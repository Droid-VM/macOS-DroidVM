#define _GNU_SOURCE
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#define PAGE 4096ULL
#define MIB (1024*1024)
static void fail(const char *s){perror(s);exit(1);}
static void rd(int f,void *b,size_t n,uint64_t off){if(pread(f,b,n,off)!=(ssize_t)n)fail("pread");}
static void wr(int f,const void *b,size_t n,uint64_t off){if(pwrite(f,b,n,off)!=(ssize_t)n)fail("pwrite");}
int main(int argc,char **argv){
 if(argc!=5){fprintf(stderr,"usage: store-to-raw STORE NEW_DISK GPT_PREFIX GPT_SUFFIX (empty seed only)\n");return 2;}
 setbuf(stdout,NULL);int src=open(argv[1],O_RDONLY);if(src<0)fail("source");
 unsigned char h[4096];rd(src,h,sizeof(h),0);if(memcmp(h,"DroidVMDataStore",16)){fprintf(stderr,"store label mismatch\n");return 1;}
 rd(src,h,sizeof(h),PAGE);uint32_t version,header;uint64_t pages;memcpy(&version,h+8,4);memcpy(&header,h+12,4);memcpy(&pages,h+16,8);
 if(memcmp(h,"SHNGDATA",8)||version!=1||header!=64||!pages||pages>268435456){fprintf(stderr,"overlay header mismatch\n");return 1;}
 uint64_t bitmap_bytes=((pages+32767)/32768)*PAGE,window=2*PAGE+bitmap_bytes,logical=pages*PAGE;
 struct stat st;if(fstat(src,&st)||st.st_size!=(off_t)(window+logical)){fprintf(stderr,"store size mismatch\n");return 1;}
 unsigned char *bitmap=malloc(bitmap_bytes),*buf=malloc(MIB),*check=malloc(MIB);if(!bitmap||!buf||!check)fail("malloc");rd(src,bitmap,bitmap_bytes,2*PAGE);
 int out=open(argv[2],O_RDWR|O_CREAT|O_EXCL,0660);if(out<0)fail("destination");if(ftruncate(out,logical+2*MIB))fail("truncate");
 for(int i=0;i<2;i++){int f=open(argv[3+i],O_RDONLY);if(f<0)fail("GPT");rd(f,buf,MIB,0);wr(out,buf,MIB,i?MIB+logical:0);close(f);}
 uint64_t copied=0,reported=0;printf("pages=%llu logical=%llu window=%llu\n",(unsigned long long)pages,(unsigned long long)logical,(unsigned long long)window);
 for(int pass=0;pass<2;pass++){
  for(uint64_t i=0;i<pages;){
   if(!(bitmap[i/8]>>(i%8)&1)){i++;continue;}
   uint64_t start=i++;while(i<pages&&i-start<256&&(bitmap[i/8]>>(i%8)&1))i++;
   size_t n=(i-start)*PAGE;rd(src,buf,n,window+start*PAGE);
   if(!pass){wr(out,buf,n,MIB+start*PAGE);copied+=n;if(copied-reported>=1024ULL*MIB){reported=copied;printf("copied_MiB=%llu\n",(unsigned long long)(copied/MIB));}}
   else{rd(out,check,n,MIB+start*PAGE);if(memcmp(buf,check,n)){fprintf(stderr,"verify mismatch page=%llu\n",(unsigned long long)start);return 1;}}
  }
  if(!pass&&fsync(out))fail("fsync");
 }
 printf("copy_and_byte_verify=PASS bytes=%llu\n",(unsigned long long)copied);close(out);close(src);free(bitmap);free(buf);free(check);return 0;
}
