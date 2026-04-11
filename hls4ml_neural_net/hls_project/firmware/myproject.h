#ifndef MYPROJECT_H_
#define MYPROJECT_H_

#include "ap_fixed.h"
#include "ap_int.h"
#include "hls_stream.h"

#include "defines.h"


// Prototype of top level function for C-synthesis
void myproject(
    input_t data_in[4],
    result_t layer7_out[3]
);

// hls-fpga-machine-learning insert emulator-defines


#endif
