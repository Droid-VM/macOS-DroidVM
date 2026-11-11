#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#define MIB (1024*1024)
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void fill(uint64_t *p,unsigned m){for(size_t i=0;i<MIB/8;i++)p[i]=((uint64_t)m*(MIB/8)+i)*UINT64_C(0x9e3779b97f4a7c15)^UINT64_C(0x20261111dadafeed);}
int main(int argc,char **argv){
 if(argc!=3)return 2;setbuf(stdout,NULL);int wr=!strcmp(argv[2],"write");
 int f=open(argv[1],wr?(O_RDWR|O_CREAT|O_EXCL):O_RDONLY,0600);if(f<0){perror("open");return 1;}
 if(fcntl(f,F_NOCACHE,1)){perror("F_NOCACHE");return 1;}
 void *b,*expected;if(posix_memalign(&b,4096,MIB)||posix_memalign(&expected,4096,MIB))return 1;
 double t=now();
 for(unsigned i=0;i<64;i++){fill(expected,i);if(wr&&pwrite(f,expected,MIB,(off_t)i*MIB)!=MIB){perror("pwrite");return 1;}}
 if(wr){double sync=now();if(fsync(f)){perror("fsync");return 1;}printf("write_64MiB_seconds=%.6f fsync_ms=%.3f\n",now()-t,(now()-sync)*1000);
  if(fcntl(f,F_FULLFSYNC)){perror("F_FULLFSYNC");return 1;}puts("F_FULLFSYNC=PASS");}
 t=now();for(unsigned i=0;i<64;i++){fill(expected,i);if(pread(f,b,MIB,(off_t)i*MIB)!=MIB||memcmp(b,expected,MIB)){fprintf(stderr,"read mismatch MiB=%u\n",i);return 1;}}
 printf("verify_64MiB=PASS seconds=%.6f phase=%s\n",now()-t,argv[2]);
 close(f);free(b);free(expected);return 0;
}
