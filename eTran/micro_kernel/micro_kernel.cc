#include <assert.h>
#include <errno.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <iostream>
#include <queue>
#include <string>
#include <unordered_map>
#include <sstream>
#include <iomanip>

#include <sys/epoll.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/resource.h>
#include <sys/un.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <arpa/inet.h>
#include <net/ethernet.h>
#include <netinet/in.h>

#include <base/atomic.h>
#include <base/compiler.h>
#include <base/lock.h>
#include <shm/shm_wrapper.h>
#include <xskbp/xsk_buffer_pool.h>
#include <runtime/app_if.h>
#include <runtime/defs.h>
#include <runtime/ebpf_if.h>
#include <utils/utils.h>

#include "nic.h"

bool force_quit = false;
static int init_step = 0;

class eTranNIC *etran_nic;

static constexpr unsigned DEFAULT_NUM_QUEUES = 20;
static constexpr unsigned DEFAULT_NUM_SHARED_QUEUES = 0;
static constexpr unsigned DEFAULT_QUEUE_LEN = 8192;
static constexpr const char *DEFAULT_IF_NAME = "ens1f1np1";

/* Global options */
static std::string opt_if_name = DEFAULT_IF_NAME;
static unsigned int opt_num_queues = DEFAULT_NUM_QUEUES;
static unsigned int opt_num_shared_queues = DEFAULT_NUM_SHARED_QUEUES;
static unsigned int opt_queue_len = DEFAULT_QUEUE_LEN;
static bool opt_napi_polling = true;
static bool opt_socket_busy_poll = false;
static bool opt_intr_affinity = true;
static bool opt_coalescing = false;

/* Homa-specific options */
int opt_workload_type = 5;

/* TCP-specific options */
/**
 * default value in linux kernel:
 * /proc/sys/net/core/rmem_default 212992
 * /proc/sys/net/core/wmem_default 212992
 */
unsigned int opt_tcp_rx_buf_size = 524288;
unsigned int opt_tcp_tx_buf_size = 524288;

static int system_init(void)
{
    std::string cmd;

    /* configure hugepages */
    cmd = "mount -t hugetlbfs nodev /dev/hugepages";
    if (!exec_cmd(cmd))
    {
        fprintf(stderr, "Failed to mount hugepages\n");
        return -1;
    }

    cmd = "echo 1024 >> "
          "/sys/devices/system/node/node0/hugepages/hugepages-2048kB/nr_hugepages";
    if (!exec_cmd(cmd))
    {
        fprintf(stderr, "Failed to configure hugepages\n");
        return -1;
    }
    /* configure memory limits */
    struct rlimit r = {RLIM_INFINITY, RLIM_INFINITY};
    if (setrlimit(RLIMIT_MEMLOCK, &r))
    {
        fprintf(stderr, "ERROR: setrlimit(RLIMIT_MEMLOCK) \"%s\"\n",
                strerror(errno));
        return -1;
    }

    return 0;
}

static int parse_mc_args(int argc, char *argv[])
{
    int opt;
    int ret = 0;

    while ((opt = getopt(argc, argv, "q:i:l:g:nbhw:Q:")) != -1)
    {
        switch (opt)
        {
        case 'n':
            opt_napi_polling = false;
            break;
        case 'b':
            opt_socket_busy_poll = true;
            break;
        case 'g':
            opt_queue_len = atoi(optarg);
            break;
        case 'q':
            opt_num_queues = atoi(optarg);
            break;
        case 'Q':
            opt_num_shared_queues = atoi(optarg);
            break;
        case 'i':
            opt_if_name = optarg;
            break;
        case 'l':
            opt_tcp_rx_buf_size = atoi(optarg);
            if (opt_tcp_rx_buf_size < 2048 || opt_tcp_rx_buf_size > 524288)
            {
                ret = -EINVAL;
                goto out;
            }
            opt_tcp_tx_buf_size = opt_tcp_rx_buf_size;
            break;
        case 'w':
            opt_workload_type = atoi(optarg);
            if (opt_workload_type < 1 || opt_workload_type > 5)
            {
                ret = -EINVAL;
                goto out;
            }
            break;
        case 'h':
        default:
            fprintf(
                stderr,
                "Global options:\n"
                "\t[-h Help]\n"
                "\t[-n Disable NAPI polling], default: enable\n"
                "\t[-b Enable socket busy poll], default: disable\n"
                "\t[-g NIC queue length], default:%u\n"
                "\t[-q Number of NIC queues], default:%u\n"
                "\t[-Q Number of shared NIC queues], default:%u\n"
                "\t[-i Interface name], default: %s\n"
                "\t[-p Transport protocol (tcp, homa)], default:tcp\n"
                "Homa options:\n"
                "\t[-w Workload type], default:5\n"
                "TCP options:\n"
                "\t[-l TCP buffer size], default:524288\n",
                DEFAULT_QUEUE_LEN,
                DEFAULT_NUM_QUEUES,
                DEFAULT_NUM_SHARED_QUEUES,
                DEFAULT_IF_NAME
            );
            ret = -EINVAL;
            goto out;
        }
    }

out:
    return ret;
}

static void shutdown_monitor(void)
{
    force_quit = true;
}

static void run_monitor(void)
{
    std::string command;

    while (!force_quit)
    {
        sleep(1);
        std::getline(std::cin, command);
        if (command == "exit")
        {
            shutdown_monitor();
            shutdown_thread();
        }
        else if (command == "dump")
        {
            dump_bpf_maps();
            dump_ring_stats();
        }
        else if (command == "kick")
        {
            kick_napi();
        }
        else
        {
            printf("Unknown command: %s\n", command.c_str());
            printf("Supported commands: exit, dump, kick\n");
        }
    }
}

int main(int argc, char *argv[])
{
    pthread_t monitor_thread;
    signal(SIGINT, [](int)
           {
        printf("Ctrl+C pressed, exiting...\n");
        shutdown_monitor();
        shutdown_thread(); });

    if (parse_mc_args(argc, argv))
    {
        fprintf(stderr, "Failed to parse arguments\n");
        exit(EXIT_FAILURE);
    }

    /* initialize system configurations */
    if (system_init())
    {
        fprintf(stderr, "System init failed\n");
        exit(EXIT_FAILURE);
    }
    printf("[Step%d] System init done.\n", ++init_step);

    /* initialize NIC */
    eTranNIC_init_params params = {
        .if_name = opt_if_name,
        .num_queues = opt_num_queues,
        .num_shared_queues = opt_num_shared_queues,
        .queue_len = opt_queue_len,
        .napi_polling = opt_napi_polling,
        .socket_busy_poll = opt_socket_busy_poll,
        .intr_affinity = opt_intr_affinity,
        .coalescing = opt_coalescing,
    };
    etran_nic = new eTranNIC(params);
    printf("[Step%d] NIC init done.\n", ++init_step);

    /* initialize microkernel context */
    if (ctx_init())
    {
        fprintf(stderr, "ctx_init failed\n");
        exit(EXIT_FAILURE);
    }
    printf("[Step%d] Microkernel context init done.\n", ++init_step);

    /* initialize eBPF configurations */
    if (ebpf_init())
    {
        goto err_1;
    }
    printf("[Step%d] eBPF init done.\n", ++init_step);

    /* launch threads */
    if (thread_init())
    {
        goto err_2;
    }
    printf("[Step%d] Threads init done.\n", ++init_step);

    pthread_create(
        &monitor_thread, nullptr,
        [](void *) -> void *
        {
            run_monitor();
            return nullptr;
        },
        nullptr);

    wait_thread();

err_2:
    ebpf_exit();
err_1:

    printf("Micro kernel exit.\n");
    return 0;
}
