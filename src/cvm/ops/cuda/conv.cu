#include "cuda_ops.h"
#include "../common.h"
#include <omp.h>

namespace cvm{
namespace runtime{

//#define BS 16
//#define FS 8

  __global__ void kernel_int32_to_int8(const int32_t *in_data, int8_t *out_data, const int n){
    int tid = threadIdx.x + blockDim.x * blockIdx.x;
    for(int64_t i = tid; i < n; i+= gridDim.x * blockDim.x){
      out_data[i] = static_cast<int8_t>(in_data[i]);
    }
  }

__global__ void kernel_transpose_i32_to_i8(const int32_t * __restrict__ in, int8_t *out, 
    const int32_t H, const int32_t W, 
    const int32_t OH, const int32_t OW){
  int bidy = blockIdx.y;
  int bidx = blockIdx.x; 
  int lidy = threadIdx.y;
  int lidx = threadIdx.x;
  __shared__ int8_t share_in[8][8];
  int y = bidy * blockDim.y + lidy;
  int x = bidx * blockDim.x + lidx;
  if(y < H && x < W){
    share_in[lidx][lidy] = (int8_t)in[y * W + x];
  }
  __syncthreads();
  int oy = bidx * blockDim.x + lidy;
  int ox = bidy * blockDim.y + lidx;
  if(oy < W && ox < H)
    out[oy * OH + ox] = share_in[lidy][lidx];
}

#define MATRIX_PAD 64
__global__ void im2col_gpu_kernel_pad(const int n, const int32_t*__restrict__ data_im,
    const int height, const int width, const int kernel_h, const int kernel_w,
    const int pad_h, const int pad_w,
    const int stride_h, const int stride_w,
    const int dilation_h, const int dilation_w,
    const int height_col, const int width_col,
    int8_t* data_col) {
  int tid = threadIdx.x + blockDim.x * blockIdx.x;
  const int cols = height_col * width_col;
  const int offset = (cols + (MATRIX_PAD-1)) / MATRIX_PAD * MATRIX_PAD;
  for(int64_t index = tid; index < n; index += gridDim.x*blockDim.x){
    const int h_index = index / width_col;
    const int h_col = h_index % height_col;
    const int w_col = index % width_col;
    const int c_im = h_index / height_col;
    const int c_col = c_im * kernel_h * kernel_w;
    const int h_offset = h_col * stride_h - pad_h;
    const int w_offset = w_col * stride_w - pad_w;
    int8_t* data_col_ptr = data_col;
    data_col_ptr += c_col * offset + h_col * width_col + w_col;//(c_col * height_col + h_col) * width_col + w_col;
    const int32_t* data_im_ptr = data_im;
    data_im_ptr += (c_im * height + h_offset) * width + w_offset;
    for (int i = 0; i < kernel_h; ++i) {
      for (int j = 0; j < kernel_w; ++j) {
        int h_im = h_offset + i * dilation_h;
        int w_im = w_offset + j * dilation_w;
        *data_col_ptr =
          (h_im >= 0 && w_im >= 0 && h_im < height && w_im < width) ?
          static_cast<int8_t>(data_im_ptr[i * dilation_h * width + j * dilation_w]) : 0;
        data_col_ptr += offset;
      }
    }
  }
}
__global__ void im2col_gpu_kernel(const int n, const int32_t* data_im,
    const int height, const int width, const int kernel_h, const int kernel_w,
    const int pad_h, const int pad_w,
    const int stride_h, const int stride_w,
    const int dilation_h, const int dilation_w,
    const int height_col, const int width_col,
    int8_t* data_col) {
  int tid = threadIdx.x + blockDim.x * blockIdx.x;
  for(int64_t index = tid; index < n; index += gridDim.x*blockDim.x){
    const int h_index = index / width_col;
    const int h_col = h_index % height_col;
    const int w_col = index % width_col;
    const int c_im = h_index / height_col;
    const int c_col = c_im * kernel_h * kernel_w;
    const int h_offset = h_col * stride_h - pad_h;
    const int w_offset = w_col * stride_w - pad_w;
    int8_t* data_col_ptr = data_col;
    data_col_ptr += (c_col * height_col + h_col) * width_col + w_col;
    const int32_t* data_im_ptr = data_im;
    data_im_ptr += (c_im * height + h_offset) * width + w_offset;
    for (int i = 0; i < kernel_h; ++i) {
      for (int j = 0; j < kernel_w; ++j) {
        int h_im = h_offset + i * dilation_h;
        int w_im = w_offset + j * dilation_w;
        *data_col_ptr =
          (h_im >= 0 && w_im >= 0 && h_im < height && w_im < width) ?
          static_cast<int8_t>(data_im_ptr[i * dilation_h * width + j * dilation_w]) : 0;
        data_col_ptr += height_col * width_col;
      }
    }
  }
}

#define TILE_WIDTH 16
template<const bool has_bias, int NUM>
__global__ void kernel_matrix_mul(
    int8_t *a, // m*k 
    int8_t *b, // k*n
    int32_t *c, // m*n
    int32_t m, int32_t k, int32_t n, int32_t *bias){
  __shared__ int8_t sharedm[TILE_WIDTH*NUM][TILE_WIDTH*NUM];
  __shared__ int8_t sharedn[TILE_WIDTH*NUM][TILE_WIDTH*NUM];
  int bx = blockIdx.x;
  int by = blockIdx.y;
  int tx = threadIdx.x;
  int ty = threadIdx.y;
  int row = by*TILE_WIDTH*NUM + ty;
  int col = bx*TILE_WIDTH*NUM + tx;
  int sum[NUM][NUM]= {{0}};

  for (int i = 0; i < (int)(ceil((float)k/TILE_WIDTH)); i+=NUM)
  {
    for(int ii = 0; ii < NUM; ++ii){
      int r_offset = ii * TILE_WIDTH;
      for(int jj = 0; jj < NUM; ++jj){
        int c_offset = jj * TILE_WIDTH;
        int arow_offset = row + r_offset;
        int acol_offset = i*TILE_WIDTH + tx + c_offset;
        int brow_offset = i*TILE_WIDTH + ty + r_offset;
        int bcol_offset =  col + c_offset;

        if(arow_offset < m && acol_offset < k)
          sharedm[ty+r_offset][tx+c_offset] = a[(arow_offset)*k + acol_offset];
        else sharedm[ty+r_offset][tx+c_offset] = 0;

        if(brow_offset < k && bcol_offset < n)
          sharedn[ty+r_offset][tx+c_offset] = b[(brow_offset)*n + bcol_offset];
        else sharedn[ty+r_offset][tx+c_offset] = 0;
      }
    }
    __syncthreads();

    for(int j = 0; j < TILE_WIDTH; j++){ 
      int8_t tm[NUM][NUM], tn[NUM][NUM];
#pragma unroll
      for(int ii = 0; ii < NUM; ++ii){
#pragma unroll
        for(int jj = 0; jj < NUM; ++jj){
          tm[ii][jj] = sharedm[ty+ii*TILE_WIDTH][j+jj*TILE_WIDTH];
          tn[ii][jj] = sharedn[j+ii*TILE_WIDTH][tx+jj*TILE_WIDTH];
        }
      }
      for(int ii = 0; ii < NUM; ++ii){
#pragma unroll
        for(int kk = 0; kk < NUM; ++kk){
#pragma unroll
          for(int jj = 0; jj < NUM; ++jj){
            sum[ii][jj] += tm[ii][kk] * tn[kk][jj];
          }
        }
      }
    }
    __syncthreads();
  }
  if(has_bias) {
    for(int ii = 0; ii < NUM; ++ii){
      int32_t bv = bias[row + ii * TILE_WIDTH];
      for(int jj = 0; jj < NUM ;++jj){
        sum[ii][jj] += bv; 
      }
    }
  }
  for(int ii = 0; ii < NUM; ++ii){
    int c_r_offset = row + ii * TILE_WIDTH;
    for(int jj = 0; jj < NUM ;++jj){
      int c_c_offset = col + jj * TILE_WIDTH;
      if(c_r_offset < m && c_c_offset < n)
        c[(c_r_offset)*n + c_c_offset] = sum[ii][jj];
    }
  }
}

template<bool has_bias>
__global__ void kernel_matrix_mul_opt(
    char4 *A, // k*m 
    char4  *B, // k*n
    int32_t *C, // m*n
    int32_t M, int32_t K, int32_t N, int32_t *bias,
    const int32_t TM, const int32_t TN, const int32_t TK){
  int lidx = threadIdx.x;
  int lidy = threadIdx.y;
  int bidx = blockIdx.x;
  int bidy = blockIdx.y;

  int aBegin = bidy * TILE_WIDTH;
  int aStep = TILE_WIDTH * (TM/4);
  int bBegin = bidx * TILE_WIDTH;
  int bStep = TILE_WIDTH * (TN/4);

  int round_K = TK / TILE_WIDTH;
  int32_t csub[4][4] = {{0}};
  for(int i = 0, a = aBegin, b = bBegin; i < round_K; ++i, a += aStep, b+= bStep){
    __shared__ char4 share_a[TILE_WIDTH][TILE_WIDTH];
    __shared__ char4 share_b[TILE_WIDTH][TILE_WIDTH];

    //int aid = a + lidy * (TM/4) + lidx;
    share_a[lidy][lidx] = A[a + lidy * (TM/4) + lidx];

    //int bid = b + lidy * (TN/4) + lidx;
    share_b[lidy][lidx] = B[b + lidy * (TN/4) + lidx];
    __syncthreads();

    for(int k = 0; k < TILE_WIDTH; ++k){
      signed char pa[4] = {share_a[k][lidy].x, share_a[k][lidy].y, share_a[k][lidy].z, share_a[k][lidy].w};
      signed char pb[4] = {share_b[k][lidx].x, share_b[k][lidx].y, share_b[k][lidx].z, share_b[k][lidx].w};
#pragma unroll
      for(int ii = 0; ii < 4; ii++){
#pragma unroll
        for(int jj = 0; jj < 4; jj++){
          csub[ii][jj] += pa[ii] * pb[jj];
        }
      }
    }
    __syncthreads();
  }

 // int c = bidy * TILE_WIDTH * N + bidx * TILE_WIDTH;
  int gidy = bidy * TILE_WIDTH + lidy;
  int gidx = bidx * TILE_WIDTH + lidx;
  for(int ii = 0; ii < 4; ii++){
    int row = (gidy * 4 + ii);
    int bv = 0;
    if(has_bias && row < M){
      bv = bias[row]; 
    }
    for(int jj = 0; jj < 4; jj++){
      int col = gidx * 4 + jj;
      if(row < M && col < N)
      C[row * N + col] = csub[ii][jj] + bv;
    }
  }
}

inline __device__ int4 vec4Add(const int a, const int4 b){
  return make_int4(
      a + b.x,
      a + b.y,
      a + b.z,
      a + b.w
      );
}
inline __device__ int4 vec4Add(const int4 a, const int4 b){
  return make_int4(
      a.x + b.x,
      a.y + b.y,
      a.z + b.z,
      a.w + b.w
      );
}
inline __device__ int4 vec4Mul(const signed char a, const char4 b){
  return make_int4(a*b.x, a*b.y, a*b.z, a*b.w);
}

texture<char4, 1, cudaReadModeElementType> texRefA;
texture<char4, 1, cudaReadModeElementType> texRefB;
template<const int BS, const int NA, const int NB, const bool hasBias>
__global__ void kernel_matrix_mul_opt6(
    const char4* __restrict__ A,
    const char4* __restrict__ B,
    int *C, // m*n
    const int32_t SM, const int32_t SK, const int32_t SN, const int32_t * __restrict__ bias,
    const int32_t TM, const int32_t TK, const int32_t TN){
  const int M = TM / 4;
  const int N = TN / 4;
  __shared__ char4 smem[BS*BS*NA + BS*BS*NB];
  char4 *cacheA = smem;
  char4 *cacheB = smem + BS*BS*NA;

  int lidx = threadIdx.x;
  int lidy = threadIdx.y;
  int bidx = blockIdx.x;
  int bidy = blockIdx.y;

  int4 csub[NA][4][NB] = {{{make_int4(0, 0, 0, 0)}}};

  for(int k = 0; k < TK; k += BS){
    //char4 ta[NA];
#pragma unroll
    for(int i = 0; i < NA; ++i){
      //ta[i] = A[(NA * bidy + i) * BS + (k + lidy) * M + lidx]; 
      //ta[i] = tex1Dfetch(texRefA, (NA * bidy + i) * BS + (k + lidy) * M + lidx); 
      cacheA[(NA*lidy+i)*BS + lidx] = A[(NA * bidy + i) * BS + (k + lidy) * M + lidx]; 
    }

    //char4 tb[NB];
#pragma unroll 
    for(int i = 0; i < NB; ++i){
      //tb[i] = B[(NB * bidx + i) * BS + (k + lidy) * N + lidx];
      //tb[i] = tex1Dfetch(texRefB, (NB * bidx + i) * BS + (k + lidy) * N + lidx);
      cacheB[(NB*lidy + i) * BS + lidx] = B[(NB * bidx + i) * BS + (k + lidy) * N + lidx];
    }

    __syncthreads();

//#pragma unroll
//    for(int i = 0; i < NA; ++i){
//      cacheA[(NA*lidy + i) * BS + lidx] = ta[i];
//    }
//#pragma unroll 
//    for(int i = 0; i < NB; ++i){
//      cacheB[(NB * lidy + i) * BS + lidx] = tb[i];
//    }    
//    __syncthreads();

    for(int i = 0; i < BS; ++i){
      char4 tmpa[NA];
#pragma unroll
      for(int ti = 0; ti < NA; ++ti){
        tmpa[ti] = cacheA[(NA * i + ti) * BS + lidy];
      }
      char4 tmpb[NA];
#pragma unroll
      for(int ti = 0; ti < NB; ++ti){
        tmpb[ti] = cacheB[(NB * i + ti) * BS + lidx];
      }

#pragma unroll
      for(int ti = 0; ti < NA; ++ti){
#pragma unroll
        for(int tj = 0; tj < NB; ++tj){
          csub[ti][0][tj] = vec4Add(csub[ti][0][tj], vec4Mul(tmpa[ti].x, tmpb[tj]));
          csub[ti][1][tj] = vec4Add(csub[ti][1][tj], vec4Mul(tmpa[ti].y, tmpb[tj]));
          csub[ti][2][tj] = vec4Add(csub[ti][2][tj], vec4Mul(tmpa[ti].z, tmpb[tj]));
          csub[ti][3][tj] = vec4Add(csub[ti][3][tj], vec4Mul(tmpa[ti].w, tmpb[tj]));
        }
      }
    }
    __syncthreads();
  }

  if(hasBias){
#pragma unroll
    for(int ti = 0; ti < NA; ++ti){
      int cy = (bidy*NA + ti) * BS + lidy;
      const int bv0 = bias[cy*4];
      const int bv1 = bias[cy*4+1];
      const int bv2 = bias[cy*4+2];
      const int bv3 = bias[cy*4+3];
#pragma unroll
      for(int tj = 0; tj < NB; ++tj){
        csub[ti][0][tj] = vec4Add(bv0, csub[ti][0][tj]);
        csub[ti][1][tj] = vec4Add(bv1, csub[ti][1][tj]);
        csub[ti][2][tj] = vec4Add(bv2, csub[ti][2][tj]);
        csub[ti][3][tj] = vec4Add(bv3, csub[ti][3][tj]);
      }
    }
  }
#pragma unroll
  for(int ti = 0; ti < NA; ++ti){
#pragma unroll
    for(int tj = 0; tj < NB; ++tj){
      int cy = (bidy*NA + ti) * BS + lidy; 
      int cx = (bidx*NB + tj) * BS + lidx;

      for(int ci = 0; ci < 4; ci++){
        int tc[4] = {csub[ti][ci][tj].x, csub[ti][ci][tj].y, csub[ti][ci][tj].z, csub[ti][ci][tj].w};
        for(int tk = 0; cy*4+ci < SM && tk < 4; tk++){
          int index = (cy * 4 + ci)*SN + cx * 4 + tk;
          if(cx * 4 + tk < SN)
            C[index] = tc[tk];
        }
      }
    }
  }
}

inline void im2col_gpu(const int32_t* data_im, const int channels,
        const int height, const int width, const int kernel_h, const int kernel_w,
        const int pad_h, const int pad_w,
        const int stride_h, const int stride_w,
        const int dilation_h, const int dilation_w,
        int8_t* data_col) {
    // We are going to launch channels * height_col * width_col kernels, each
    // kernel responsible for copying a single-channel grid.
    int height_col = (height + 2 * pad_h -
            (dilation_h * (kernel_h - 1) + 1)) / stride_h + 1;
    int width_col = (width + 2 * pad_w -
            (dilation_w * (kernel_w - 1) + 1)) / stride_w + 1;
    int num_kernels = channels* height_col* width_col;
    int threads = 256;
    int blocks = (num_kernels + threads - 1) / threads;
    im2col_gpu_kernel_pad<<<blocks, threads>>>(
                num_kernels, data_im, height, width, kernel_h, kernel_w, pad_h,
                pad_w, stride_h, stride_w, dilation_h, dilation_w, height_col,
                width_col, data_col);
}

const char* cuda_conv2d(
    int32_t *input, int32_t i_n, int32_t i_c, int32_t i_h, int32_t i_w,
    int32_t *filter, int32_t f_n, int32_t f_c, const int32_t f_h, const int32_t f_w,
    int32_t *bias,
    const int32_t padding_h, const int32_t padding_w,
    const int32_t stride_h, const int32_t stride_w,
    const int32_t dilation_h, const int32_t dilation_w,
    int32_t groups,
    int32_t *output, int32_t o_n, int32_t o_c, int32_t o_h, int32_t o_w, 
    int32_t device_id,
    int32_t *ext_space, 
    int32_t ext_space_size, int& error_code){

  int32_t *dev_i = input, *dev_f = filter, *dev_o = output, *dev_b = bias;

  const int M = o_c;
  const int TM = (M + (MATRIX_PAD-1)) / MATRIX_PAD * MATRIX_PAD;
  const int K = i_c * f_h * f_w;
  const int TK = (K + (MATRIX_PAD-1)) / MATRIX_PAD * MATRIX_PAD;
  const int N = o_h * o_w;
  const int TN = (N + (MATRIX_PAD-1)) / MATRIX_PAD * MATRIX_PAD;
  const int BS = 8;
  const int NA = 2;
  const int NB = 2;
  dim3 bDim1(BS, BS, 1);
  //int gh = TM/4 / BS / NA;
  //int gw = TN/4 / BS / NB;
  dim3 bDim2(TILE_WIDTH, TILE_WIDTH, 1);
  int gh = TM / 64;
  int gw = TN / 64;
  dim3 gDim(gw, gh, 1);

  //double start = omp_get_wtime();
  cudaMemset(ext_space, 0, sizeof(int32_t)*ext_space_size);
  int8_t *d_f = (int8_t*)ext_space;
  int8_t *d_col = d_f + TM * TK;

 // int blockSize = 256;
 // int gridSize = getGridSize(fn, blockSize);
  //kernel_int32_to_int8<<<gridSize, blockSize>>>(dev_f, d_f, fn);
  dim3 bSize(8, 8, 1);
  dim3 gSize((K+7)/8, (M+7)/8, 1);
  kernel_transpose_i32_to_i8<<<gSize, bSize>>>(dev_f, d_f, M, K, TM, TK);
  //cudaDeviceSynchronize();
  //double tran_end = omp_get_wtime();
  //printf("%d %d %d %d transpose: %.5f\n", M, K, TM, TK, tran_end-start);
  
  //cudaBindTexture(0, texRefA, (char4*)d_f);
  //cudaBindTexture(0, texRefB, (char4*)d_col);
  for(int i = 0; i < o_n; i++){
    im2col_gpu(dev_i + i * i_c * i_h * i_w,
        i_c, i_h, i_w, f_h, f_w, padding_h, padding_w, stride_h, stride_w, 
        dilation_h, dilation_w, d_col);

  //  cudaDeviceSynchronize();
  //  double im2col_end = omp_get_wtime();
  //  printf("%d %d %d im2col: %.5f\n", TM, TK, TN, im2col_end-tran_end);

    if(dev_b == NULL){
      if(true)//(TM > 256 && TN > 256)
        kernel_matrix_mul_opt6<BS, NA, NB, false><<<gDim, bDim1>>>((char4*)d_f, (char4*)d_col, (dev_o + i * o_c * o_h * o_w), M, K, N, dev_b, TM, TK, TN);
      else
        kernel_matrix_mul_opt<false><<<gDim, bDim2>>>((char4*)d_f, (char4*)d_col, dev_o + i * o_c * o_h * o_w, M, K, N, dev_b, TM, TN, TK);
    }
    else{
      if(true)//(TM > 256 && TN > 256)
        kernel_matrix_mul_opt6<BS, NA, NB, true><<<gDim, bDim1>>>((char4*)d_f, (char4*)d_col, (dev_o + i * o_c * o_h * o_w), M, K, N, dev_b, TM, TK, TN);
      else
        kernel_matrix_mul_opt<true><<<gDim, bDim2>>>((char4*)d_f, (char4*)d_col, dev_o + i * o_c * o_h * o_w, M, K, N, dev_b, TM, TN, TK);
    }
  //  cudaDeviceSynchronize();
  //  double end = omp_get_wtime();
  //  printf("%d %d %d matrix_mul: %.5f\n", TM, TK, TN, end-im2col_end);
  }

  //cudaUnbindTexture(texRefA);
  //cudaUnbindTexture(texRefB);
  print_to_file(dev_i, o_n * i_c* i_h * i_w, "conv2d_x.txt");
  print_to_file(dev_o, o_n * o_c * o_h * o_w, "conv2d.txt");
  //return check_cuda_error(error);
  return "";
}

template<int BS>
__global__ void kernel_depthwise_conv2d(
    const int32_t * __restrict__ input, int32_t i_n, int32_t i_c, int32_t i_h, int32_t i_w,
    const int32_t * __restrict__ filter, int32_t f_n, int32_t f_c, int32_t f_h, int32_t f_w,
    const int32_t * __restrict__ bias,
    int32_t padding_h, int32_t padding_w,
    int32_t stride_h, int32_t stride_w,
    int32_t dilation_h, int32_t dilation_w, 
    int32_t groups,
    int32_t *output, int32_t o_n, int32_t o_c, int32_t o_h, int32_t o_w)
{
  int g_x = blockDim.x * blockIdx.x + threadIdx.x;
  int l_y = threadIdx.y; 
  int l_x = threadIdx.x;
  int tmp_f_h = (f_h - 1) * dilation_h + 1; // for dilation, to be optimized
  int tmp_f_w = (f_w - 1) * dilation_w + 1;
  int tmp_o_h = i_h + 2 * padding_h - tmp_f_h + 1; // for stride
  int tmp_o_w = i_w + 2 * padding_w - tmp_f_w + 1;
  int perBlockOneImageY = (tmp_o_h+BS-1) / BS;
  int perBlockOneImageX = (tmp_o_w+BS-1) / BS;
  int l_o_c = blockIdx.y / perBlockOneImageY;
  int l_f_c = l_o_c % o_c;
  int l_o_hi = blockIdx.y % perBlockOneImageY;
  int l_o_wi = blockIdx.x % perBlockOneImageX;
  int l_o_h = l_o_hi * BS + l_y;
  //    int l_o_w = l_o_wi * BS + l_x;
  if(l_o_h >= tmp_o_h || g_x >= tmp_o_w) return;

  const int32_t F_H = f_h;
  const int32_t F_W = f_w;
  //    __shared__ int32_t shared_i[BS + F_H - 1][BS + F_W - 1];
  int32_t sih = BS + tmp_f_h - 1;
  int32_t siw = BS + tmp_f_w - 1;
  extern __shared__ int32_t  share[];
  int32_t *shared_i = (int32_t*)share; 
  int32_t *shared_f = &share[sih * siw];

  int32_t sum = 0; 
  int min_s_y = (l_o_hi+1) * BS <= tmp_o_h ? BS : tmp_o_h%BS;
  int min_s_x = (l_o_wi+1) * BS <= tmp_o_w ? BS : tmp_o_w%BS;

  //load input to shared
  int l_i_h = l_o_h - padding_h;
  int i_y = l_o_c * i_h + l_i_h;
  int i_x = g_x - padding_w;
  // 0~2-> -1~1
  if(l_i_h < 0 || i_x < 0 || l_i_h >= i_h || i_x >= i_w)
    shared_i[l_y*siw + l_x] = 0;
  else
    shared_i[l_y*siw + l_x] = input[i_y * i_w + i_x];

  if(l_y < tmp_f_h-1){
    for(int i = l_y; i < tmp_f_h-1; i+=min_s_y){
      if(l_i_h+min_s_y+i-l_y < 0 || i_x < 0 || l_i_h+min_s_y+i-l_y >= i_h || i_x >= i_w)
        shared_i[(i+min_s_y)*siw + l_x] = 0;
      else
        shared_i[(i + min_s_y)*siw + l_x] = input[(i_y + min_s_y + i - l_y) * i_w + i_x]; 
    }
  }
  if(l_x < tmp_f_w-1){
    for(int i = l_x; i < tmp_f_w-1; i+= min_s_x){
      if(l_i_h < 0 || i_x+min_s_x+i-l_x < 0 || l_i_h >= i_h || i_x+min_s_x+i-l_x >= i_w)
        shared_i[l_y * siw + i+min_s_x] = 0;
      else
        shared_i[l_y * siw + i + min_s_x] = input[i_y * i_w + i_x + min_s_x + i - l_x];
    }
  }
  if(l_y < tmp_f_h-1 && l_x < tmp_f_w-1){
    for(int i = l_y; i < tmp_f_h-1; i+=min_s_y){
      for(int j = l_x; j < tmp_f_w-1; j+=min_s_x){
        if(l_i_h+min_s_y+i-l_y < 0 || i_x+min_s_x+j-l_x < 0 || l_i_h+min_s_y+i-l_y >= i_h || i_x+min_s_x+j-l_x >= i_w)
          shared_i[(i+min_s_y) * siw + j+min_s_x] = 0;
        else
          shared_i[(i+min_s_y) * siw + j+min_s_x] = input[(i_y+min_s_y + i-l_y)*i_w + i_x + min_s_x + j - l_x];
      }
    }
  }

  //load filter to shared;
  if(l_y < F_H && l_x < F_W){
    for(int i = l_y; i < F_H; i+= min_s_y)
      for(int j = l_x; j < F_W; j+=min_s_x)
        shared_f[i*F_W + j] = filter[l_f_c * F_H * F_W + i * F_W + j];
  }
  __syncthreads();

  for(int fy = 0; fy < F_H; fy++){
    for(int fx = 0; fx < F_W; fx++){
      sum += shared_i[(l_y+fy*dilation_h)*siw + l_x+fx*dilation_w] * shared_f[fy*F_W + fx];
    }
  } 
  __syncthreads();

  if(l_o_h % stride_h == 0 && g_x % stride_w == 0){
    //int oi = l_o_c * o_h * o_w + l_o_h * o_w + g_x;
    int oi = l_o_c * o_h * o_w + l_o_h/stride_h * o_w + g_x/stride_w;
    output[oi] = sum + (bias != NULL ? bias[l_o_c%o_c] : 0);
  }
}
__global__ void kernel_depthwise_conv2d_no_shared(
    int32_t *input, int32_t i_n, int32_t i_c, int32_t i_h, int32_t i_w,
    int32_t *filter, int32_t f_n, int32_t f_c, int32_t f_h, int32_t f_w,
    int32_t *bias,
    int32_t padding_h, int32_t padding_w,
    int32_t stride_h, int32_t stride_w,
    int32_t dilation_h, int32_t dilation_w, 
    int32_t groups,
    int32_t *output, int32_t o_n, int32_t o_c, int32_t o_h, int32_t o_w){
  int32_t gy = threadIdx.y + blockIdx.y * blockDim.y;
  int32_t gx = threadIdx.x + blockIdx.x * blockDim.x;
  int32_t l_o_h = gy % o_h;
  int32_t l_o_c = gy / o_h % o_c;
  int32_t l_o_n = gy / (o_h * o_c);
  if(gy < o_n * o_c * o_h && gx < o_w){
    int32_t sum = 0;
    for(int fy = 0; fy < f_h; ++fy){
      for(int fx = 0; fx < f_w; ++fx){
        int32_t l_i_h = l_o_h * stride_h + fy * dilation_h - padding_h;
        int32_t l_i_w = gx * stride_w + fx * dilation_w - padding_w;
        int32_t x;
        if(l_i_h < 0 || l_i_w < 0 || l_i_h >= i_h || l_i_w >= i_w)
          //x = 0;
          continue;
        x = input[l_o_n * i_c * i_h * i_w + l_o_c * i_h * i_w + l_i_h * i_w + l_i_w];
        sum += x * filter[l_o_c * f_h * f_w + fy * f_w + fx];
      }
    }
    output[gy * o_w + gx] = sum + (bias != NULL ? bias[l_o_c] : 0);
  }
}

const char* cuda_depthwise_conv2d(
    int32_t *input, int32_t i_n, int32_t i_c, int32_t i_h, int32_t i_w,
    int32_t *filter, int32_t f_n, int32_t f_c, int32_t f_h, int32_t f_w,
    int32_t *bias,
    int32_t padding_h, int32_t padding_w,
    int32_t stride_h, int32_t stride_w,
    int32_t dilation_h, int32_t dilation_w,
    int32_t groups,
    int32_t *output, int32_t o_n, int32_t o_c, int32_t o_h, int32_t o_w, int32_t device_id, int& error_code){
  int32_t *dev_i = input, *dev_f = filter, *dev_o = output, *dev_b = bias;

  const int BS = 16;
  int b_h = BS;
  int b_w = BS;
  int tmp_f_h = (f_h - 1) * dilation_h + 1; // for dilation, to be optimized
  int tmp_f_w = (f_w - 1) * dilation_w + 1;
  int tmp_o_h = i_h + 2 * padding_h - tmp_f_h + 1; //for stride > 1
  int tmp_o_w = i_w + 2 * padding_w - tmp_f_w + 1;
  int32_t g_h = o_n * o_c * ((tmp_o_h + b_h - 1) / b_h); 
  int32_t g_w = (tmp_o_w + b_w - 1) / b_w;
  dim3 bDim(b_w, b_h, 1);
  dim3 gDim(g_w, g_h, 1);
  kernel_depthwise_conv2d_no_shared<<<gDim, bDim>>>(
      dev_i, i_n, i_c, i_h, i_w,
      dev_f, f_n, f_c, f_h, f_w,
      dev_b, 
      padding_h, padding_w,
      stride_h, stride_w,
      dilation_h, dilation_w,
      groups,
      dev_o, o_n, o_c, o_h, o_w);
  cudaError_t error = cudaGetLastError();
  if(cudaSuccess != error){
    error_code = ERROR_KERNEL;
  }
  return check_cuda_error(error);
}
__global__ void kernel_groupwise_conv2d_no_shared(
    int32_t *input, int32_t i_n, int32_t i_c, int32_t i_h, int32_t i_w,
    int32_t *filter, int32_t f_n, int32_t f_c, int32_t f_h, int32_t f_w,
    int32_t *bias,
    int32_t padding_h, int32_t padding_w,
    int32_t stride_h, int32_t stride_w,
    int32_t dilation_h, int32_t dilation_w, 
    int32_t groups,
    int32_t *output, int32_t o_n, int32_t o_c, int32_t o_h, int32_t o_w){
  int32_t gy = threadIdx.y + blockIdx.y * blockDim.y;
  int32_t gx = threadIdx.x + blockIdx.x * blockDim.x;
  int32_t l_o_h = gy % o_h;
  int32_t l_o_c = gy / o_h % o_c;
  int32_t l_o_n = gy / (o_h * o_c);
  const int32_t ochannels_per_group = o_c / groups;
  const int32_t ichannels_per_group = i_c / groups;
  if(gy < o_n * o_c * o_h && gx < o_w){
    int32_t sum = 0;
    int32_t ic = l_o_c / ochannels_per_group * ichannels_per_group;
    for(int tic = 0; tic < ichannels_per_group; ++tic){
      for(int fy = 0; fy < f_h; ++fy){
        for(int fx = 0; fx < f_w; ++fx){
          int32_t l_i_h = l_o_h * stride_h + fy * dilation_h - padding_h;
          int32_t l_i_w = gx * stride_w + fx * dilation_w - padding_w;
          int32_t x;
          if(l_i_h < 0 || l_i_w < 0 || l_i_h >= i_h || l_i_w >= i_w)
            continue;
          x = input[l_o_n * i_c * i_h * i_w + (ic+tic) * i_h * i_w + l_i_h * i_w + l_i_w];
          sum += x * filter[l_o_c * f_h * f_w * f_c + tic * f_h * f_w + fy * f_w + fx];
        }
      }
    }
    output[gy * o_w + gx] = sum + (bias != NULL ? bias[l_o_c] : 0);
  }
}
const char* cuda_groupwise_conv2d(
    int32_t *input, int32_t i_n, int32_t i_c, int32_t i_h, int32_t i_w,
    int32_t *filter, int32_t f_n, int32_t f_c, int32_t f_h, int32_t f_w,
    int32_t *bias,
    int32_t padding_h, int32_t padding_w,
    int32_t stride_h, int32_t stride_w,
    int32_t dilation_h, int32_t dilation_w,
    int32_t groups,
    int32_t *output, int32_t o_n, int32_t o_c, int32_t o_h, int32_t o_w, int32_t device_id, int& error_code){
  int32_t *dev_i = input, *dev_f = filter, *dev_o = output, *dev_b = bias;

  const int BS = 16;
  int b_h = BS;
  int b_w = BS;
  int tmp_f_h = (f_h - 1) * dilation_h + 1; 
  int tmp_f_w = (f_w - 1) * dilation_w + 1;
  int tmp_o_h = i_h + 2 * padding_h - tmp_f_h + 1; 
  int tmp_o_w = i_w + 2 * padding_w - tmp_f_w + 1;
  int32_t g_h = o_n * o_c * ((tmp_o_h + b_h - 1) / b_h); 
  int32_t g_w = (tmp_o_w + b_w - 1) / b_w;
  dim3 bDim(b_w, b_h, 1);
  dim3 gDim(g_w, g_h, 1);
  kernel_groupwise_conv2d_no_shared<<<gDim, bDim>>>(
      dev_i, i_n, i_c, i_h, i_w,
      dev_f, f_n, f_c, f_h, f_w,
      dev_b, 
      padding_h, padding_w,
      stride_h, stride_w,
      dilation_h, dilation_w,
      groups,
      dev_o, o_n, o_c, o_h, o_w);
  cudaError_t error = cudaGetLastError();
  if(cudaSuccess != error){
    error_code = ERROR_KERNEL;
  }
  return check_cuda_error(error);
}

__global__ void kernel_max_pool_no_shared(
    int32_t *input, int32_t i_n, int32_t i_c, int32_t i_h, int32_t i_w,
    int32_t f_h, int32_t f_w,
    int32_t padding_h, int32_t padding_w,
    int32_t stride_h, int32_t stride_w,
    int32_t *output, int32_t o_n, int32_t o_c, int32_t o_h, int32_t o_w){
  int32_t gy = threadIdx.y + blockIdx.y * blockDim.y;
  int32_t gx = threadIdx.x + blockIdx.x * blockDim.x;
  int32_t l_o_h = gy % o_h;
  int32_t l_o_c = gy / o_h % o_c;
  int32_t l_o_n = gy / (o_h * o_c);
  if(gy < o_n * o_c * o_h && gx < o_w){
    int32_t minV = (int32_t)1 << 31;
    int32_t maxV = minV;
    for(int fy = 0; fy < f_h; ++fy){
      for(int fx = 0; fx < f_w; ++fx){
        int32_t l_i_h = l_o_h * stride_h + fy  - padding_h;
        int32_t l_i_w = gx * stride_w + fx - padding_w;
        int32_t x;
        if(l_i_h < 0 || l_i_w < 0 || l_i_h >= i_h || l_i_w >= i_w)
          x = minV;
        else x = input[l_o_n * i_c * i_h * i_w + l_o_c * i_h * i_w + l_i_h * i_w + l_i_w];
        maxV = maxV < x ? x : maxV;
      }
    }
    output[gy * o_w + gx] = maxV;
  }
}
const char* cuda_max_pool(
    int32_t *input, int32_t i_n, int32_t i_c, int32_t i_h, int32_t i_w,
    const int32_t f_h, const int32_t f_w,
    int32_t padding_h, int32_t padding_w,
    int32_t stride_h, int32_t stride_w,
    int32_t *output, int32_t o_n, int32_t o_c, int32_t o_h, int32_t o_w, int32_t device_id, int& error_code){
  int32_t *dev_i = input, *dev_o = output;

  const int BS = 16;
  int b_h = BS;
  int b_w = BS;
  int32_t g_h = o_n * o_c * ((o_h + b_h - 1) / b_h); 
  int32_t g_w = (o_w + b_w - 1) / b_w;
  dim3 bDim(b_w, b_h, 1);
  dim3 gDim(g_w, g_h, 1);
  kernel_max_pool_no_shared<<<gDim, bDim>>>(
      dev_i, i_n, i_c, i_h, i_w,
      f_h, f_w,
      padding_h, padding_w, 
      stride_h, stride_w,
      dev_o, o_n, o_c, o_h, o_w);
  cudaError_t error = cudaGetLastError();
  if(cudaSuccess != error){
    error_code = ERROR_KERNEL;
  }
  return check_cuda_error(error);
}
}
}
