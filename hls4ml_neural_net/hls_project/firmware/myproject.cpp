#include <iostream>

#include "myproject.h"
#include "parameters.h"


void myproject(
    input_t data_in[4],
    result_t layer7_out[3]
) {

    // hls-fpga-machine-learning insert IO
    #pragma HLS ARRAY_RESHAPE variable=data_in complete dim=0
    #pragma HLS ARRAY_PARTITION variable=layer7_out complete dim=0
    #pragma HLS INTERFACE ap_vld port=data_in,layer7_out 
    #pragma HLS PIPELINE

    // hls-fpga-machine-learning insert load weights
#ifndef __SYNTHESIS__
    static bool loaded_weights = false;
    if (!loaded_weights) {
        nnet::load_weights_from_txt<dense_0_weight_t, 64>(w2, "w2.txt");
        nnet::load_weights_from_txt<dense_0_bias_t, 16>(b2, "b2.txt");
        nnet::load_weights_from_txt<dense_1_weight_t, 128>(w4, "w4.txt");
        nnet::load_weights_from_txt<dense_1_bias_t, 8>(b4, "b4.txt");
        nnet::load_weights_from_txt<output_weight_t, 24>(w6, "w6.txt");
        nnet::load_weights_from_txt<output_bias_t, 3>(b6, "b6.txt");
        loaded_weights = true;    }
#endif
    // ****************************************
    // NETWORK INSTANTIATION
    // ****************************************

    // hls-fpga-machine-learning insert layers

    dense_0_result_t layer2_out[16];
    #pragma HLS ARRAY_PARTITION variable=layer2_out complete dim=0

    layer3_t layer3_out[16];
    #pragma HLS ARRAY_PARTITION variable=layer3_out complete dim=0

    dense_1_result_t layer4_out[8];
    #pragma HLS ARRAY_PARTITION variable=layer4_out complete dim=0

    layer5_t layer5_out[8];
    #pragma HLS ARRAY_PARTITION variable=layer5_out complete dim=0

    layer6_t layer6_out[3];
    #pragma HLS ARRAY_PARTITION variable=layer6_out complete dim=0

    nnet::dense<input_t, dense_0_result_t, config2>(data_in, layer2_out, w2, b2); // dense_0

    nnet::relu<dense_0_result_t, layer3_t, relu_config3>(layer2_out, layer3_out); // dense_0_relu

    nnet::dense<layer3_t, dense_1_result_t, config4>(layer3_out, layer4_out, w4, b4); // dense_1

    nnet::relu<dense_1_result_t, layer5_t, relu_config5>(layer4_out, layer5_out); // dense_1_relu

    nnet::dense<layer5_t, layer6_t, config6>(layer5_out, layer6_out, w6, b6); // output

    nnet::softmax<layer6_t, result_t, softmax_config7>(layer6_out, layer7_out); // output_softmax

}

