/* SPDX-License-Identifier: MIT */
#include "vendor/cubiomes/finders.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <errno.h>
#include <string.h>

static int number(const char *s, int64_t *out) {
    char *end; errno=0;
    if (!s || !*s) return 0;
    const char *p=s; if (*p=='-' || *p=='+') p++;
    if (!*p) return 0;
    for (;*p;p++) if (*p<'0' || *p>'9') return 0;
    long long n=strtoll(s,&end,10);
    if(errno || *end) return 0;
    *out=(int64_t)n; return 1;
}
static int floor_div(int a,int b) { int q=a/b; return q-(a%b<0); }
int main(int argc,char **argv) {
    if(argc!=4) { fprintf(stderr,"Usage: city-engine SIGNED_SEED BORDER VERSION(1.19|1.20|1.21)\n"); return 2; }
    int64_t signed_seed,border;
    if(!number(argv[1],&signed_seed) || !number(argv[2],&border) || border<1 || border>15900) {
        fprintf(stderr,"Seed must be a signed 64-bit integer; border must be 1..15900.\n"); return 2;
    }
    int mc=!strcmp(argv[3],"1.19")?MC_1_19:!strcmp(argv[3],"1.20")?MC_1_20:!strcmp(argv[3],"1.21")?MC_1_21:0;
    if(!mc) { fprintf(stderr,"Unsupported generator version.\n"); return 2; }
    Generator g; setupGenerator(&g,mc,0);
    uint64_t seed=(uint64_t)signed_seed;
    applySeed(&g,DIM_OVERWORLD,seed);
    StructureConfig config;
    if(!getStructureConfig(Ancient_City,mc,&config)) return 3;
    int step=config.regionSize*16,lo=floor_div(-(int)border,step),hi=floor_div((int)border,step);
    int count=0;
    for(int rx=lo;rx<=hi;rx++) {
        for(int rz=lo;rz<=hi;rz++) {
            Pos p;
            if(!getStructurePos(Ancient_City,mc,seed,rx,rz,&p)) continue;
            if(abs(p.x)>border || abs(p.z)>border) continue;
            if(!isViableStructurePos(Ancient_City,&g,p.x,p.z,0)) continue;
            if(!isViableStructureTerrain(Ancient_City,&g,p.x,p.z)) continue;
            if(count++) printf("; ");
            printf("%d %d",p.x,p.z);
        }
        fprintf(stderr,"PROGRESS %d\n",100*(rx-lo+1)/(hi-lo+1)); fflush(stderr);
    }
    printf("\n"); fprintf(stderr,"COUNT %d\n",count);
    return 0;
}
