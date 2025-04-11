#ifndef NIC_H
#define NIC_H

#include "xskbp/xsk_buffer_pool.h"
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include <intf/intf_ebpf.h>
#include <runtime/ebpf_if.h>
#include <utils/utils.h>

struct eTranNIC_init_params {
    std::string if_name;
    unsigned int num_queues;
    unsigned int num_shared_queues;
    unsigned int queue_len;
    bool napi_polling;
    bool socket_busy_poll;
    bool intr_affinity;
    bool coalescing;
};

class eTranNIC
{
public:
    /* interface name */
    std::string _if_name;
    /* local IPv4 address */
    uint32_t _local_ip;
    /* number of NIC queues */
    unsigned int _num_queues;
    /* number of shared NIC queues */
    unsigned int _num_shared_queues;
    /* NIC queue length */
    unsigned int _queue_len;
    /* enable NAPI polling */
    bool _napi_polling;
    /* enable socket busy poll */
    bool _socket_busy_poll;
    /* enable interrupt affinity */
    bool _intr_affinity;
    /* enable coalescing */
    bool _coalescing;

    /* NIC queue information */
    nic_queue_info _nic_queues[MAX_NIC_QUEUES];

    std::vector<unsigned int> _free_exclusive_qids,
                              _shared_qids;

    bool _shared_queues_ready;
    struct buffer_pool_wrapper *_shared_bpw;

    /* available keys in BPF_MAP_TYPE_XSKMAP, starts from zero */
    std::vector<int> _available_xsk_keys;

    eTranNIC(const eTranNIC_init_params &params) :
        _if_name(params.if_name),
        _num_queues(params.num_queues),
        _num_shared_queues(params.num_shared_queues),
        _queue_len(params.queue_len),
        _napi_polling(params.napi_polling),
        _socket_busy_poll(params.socket_busy_poll),
        _intr_affinity(params.intr_affinity),
        _coalescing(params.coalescing),
        _shared_queues_ready(false),
        _shared_bpw(nullptr)
    {
        if (_num_queues < _num_shared_queues) {
            _num_shared_queues = _num_queues;
            fprintf(stderr, "Too many shared queues, truncating to %u", _num_queues);
        }
        if (create_nic()) {
            throw std::runtime_error("Failed to create NIC");
        }

        for (unsigned int i = 0; i < _num_queues; i++) {
            _nic_queues[i].qid = i;
            if (i >= _num_queues - _num_shared_queues) {
                // [_num_queues - _num_shared_queues, _num_queues) are shared
                _nic_queues[i].is_shared = true;
                _shared_qids.push_back(i);
            } else {
                _nic_queues[i].is_shared = false;
                _free_exclusive_qids.push_back(i);
            }
        }

        _available_xsk_keys.resize(MAX_XSK_FD);
        for (int i = 0; i < MAX_XSK_FD; i++) {
            _available_xsk_keys[i] = i;
        }
    }

    ~eTranNIC()
    {
        destroy_nic();
    }

private:
    int create_nic(void);
    void destroy_nic(void);
};

#endif // NIC_H
