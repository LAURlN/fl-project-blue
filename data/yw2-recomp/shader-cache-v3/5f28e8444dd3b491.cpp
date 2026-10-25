// Clockwork native shader cache ABI 3; generated from a privately supplied program.
#include <cmath>
#include <cstdint>
#ifdef _WIN32
#define SHADER_API __declspec(dllexport)
#else
#define SHADER_API
#endif
struct V { float v[4]; float &operator[](int i) { return v[i]; } float operator[](int i) const { return v[i]; } };
static float mul(float a,float b) { float r=a*b; return std::isnan(r)&&!std::isnan(a)&&!std::isnan(b)?0.0f:r; }
extern "C" SHADER_API void shader(const V *f,const uint8_t *iu,uint32_t b,const V *in,V *out,
void *emitter,V *(*emit)(void *,const V *,uint32_t),V *tmp_state,int32_t *addr_state,bool *cond_state) {
V local_tmp[16]={}; int32_t local_addr[3]={}; bool local_cond[2]={};
V *tmp=tmp_state?tmp_state:local_tmp; int32_t *addr=addr_state?addr_state:local_addr;
bool *cond=cond_state?cond_state:local_cond; const V ones={{1,1,1,1}};
struct F { uint32_t final_pc,return_pc,loop_pc; uint8_t repeat,increment; bool loop; } stack[16];
int sp=0; uint32_t pc=437; int steps=0;
auto src=[&](uint32_t reg,int32_t offset)->const V& {
if(reg<16)return in[reg]; if(reg<32)return tmp[reg-16];
if(offset<-128||offset>127)offset=0; int32_t i=(int32_t(reg-32)+offset)&127; return i<96?f[i]:ones; };
auto push=[&](F v){if(sp<16)stack[sp++]=v;};
dispatch:
while(sp>0&&pc==stack[sp-1].final_pc) {
F &v=stack[sp-1]; if(v.loop) {addr[2]+=v.increment; if(v.repeat--==0){pc=v.return_pc;sp--;}else pc=v.loop_pc;}
else {pc=v.return_pc;sp--;}}
switch(pc) {
case 437:goto L437;
case 438:goto L438;
case 439:goto L439;
case 440:goto L440;
case 441:goto L441;
case 442:goto L442;
case 443:goto L443;
case 444:goto L444;
case 445:goto L445;
case 446:goto L446;
case 447:goto L447;
case 448:goto L448;
case 449:goto L449;
case 450:goto L450;
case 451:goto L451;
case 452:goto L452;
case 453:goto L453;
case 454:goto L454;
case 455:goto L455;
case 456:goto L456;
case 457:goto L457;
case 458:goto L458;
case 459:goto L459;
case 460:goto L460;
case 461:goto L461;
case 462:goto L462;
case 463:goto L463;
case 464:goto L464;
case 465:goto L465;
case 466:goto L466;
case 467:goto L467;
case 468:goto L468;
case 469:goto L469;
case 470:goto L470;
case 471:goto L471;
case 472:goto L472;
case 473:goto L473;
case 474:goto L474;
case 475:goto L475;
case 476:goto L476;
case 477:goto L477;
case 478:goto L478;
case 479:goto L479;
case 480:goto L480;
case 481:goto L481;
case 482:goto L482;
case 483:goto L483;
case 484:goto L484;
default:return;}
L437:if(++steps>0x40000)return;{
const V &as=src(0,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L438;
}
L438:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(6,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L439;
}
L439:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[0][0]=r[0];out[0][1]=r[1];out[0][2]=r[2];out[0][3]=r[3];goto L440;
}
L440:if(++steps>0x40000)return;{
const V &as=src(1,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[1][0]=r[0];out[1][1]=r[1];out[1][2]=r[2];out[1][3]=r[3];goto L441;
}
L441:if(++steps>0x40000)return;{
const V &as=src(2,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[2][0]=r[0];out[2][1]=r[1];out[2][2]=r[2];out[2][3]=r[3];goto L442;
}
L442:if(++steps>0x40000)return;{
const V &as=src(3,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[3][0]=r[0];out[3][1]=r[1];out[3][2]=r[2];out[3][3]=r[3];goto L443;
}
L443:if(++steps>0x40000)return;{
const V &as=src(4,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L444;
}
L444:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[1],as[1]}};
const V &vs=src(5,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L445;
}
L445:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[1],as[1]}};
const V &vs=src(5,0); V v={{vs[2],vs[3],vs[3],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L446;
}
L446:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[4][0]=r[0];out[4][1]=r[1];out[4][2]=r[2];out[4][3]=r[3];goto L447;
}
L447:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[5][0]=r[0];out[5][1]=r[1];out[5][2]=r[2];out[5][3]=r[3];goto L448;
}
L448:if(++steps>0x40000)return;{
if(emit)out=emit(emitter,out,2885681152u);goto L449;
}
L449:if(++steps>0x40000)return;{
if(emit)out=emit(emitter,out,2818572288u);goto L450;
}
L450:if(++steps>0x40000)return;{
const V &as=src(0,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L451;
}
L451:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{-vs[0],-vs[1],-vs[2],-vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L452;
}
L452:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[0][0]=r[0];out[0][1]=r[1];out[0][2]=r[2];out[0][3]=r[3];goto L453;
}
L453:if(++steps>0x40000)return;{
const V &as=src(1,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[1][0]=r[0];out[1][1]=r[1];out[1][2]=r[2];out[1][3]=r[3];goto L454;
}
L454:if(++steps>0x40000)return;{
const V &as=src(2,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[2][0]=r[0];out[2][1]=r[1];out[2][2]=r[2];out[2][3]=r[3];goto L455;
}
L455:if(++steps>0x40000)return;{
const V &as=src(3,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[3][0]=r[0];out[3][1]=r[1];out[3][2]=r[2];out[3][3]=r[3];goto L456;
}
L456:if(++steps>0x40000)return;{
const V &as=src(4,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L457;
}
L457:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[1],as[1]}};
const V &vs=src(5,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L458;
}
L458:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[4][0]=r[0];out[4][1]=r[1];out[4][2]=r[2];out[4][3]=r[3];goto L459;
}
L459:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[5][0]=r[0];out[5][1]=r[1];out[5][2]=r[2];out[5][3]=r[3];goto L460;
}
L460:if(++steps>0x40000)return;{
if(emit)out=emit(emitter,out,2902458368u);goto L461;
}
L461:if(++steps>0x40000)return;{
if(emit)out=emit(emitter,out,2818572288u);goto L462;
}
L462:if(++steps>0x40000)return;{
const V &as=src(0,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L463;
}
L463:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L464;
}
L464:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[0][0]=r[0];out[0][1]=r[1];out[0][2]=r[2];out[0][3]=r[3];goto L465;
}
L465:if(++steps>0x40000)return;{
const V &as=src(1,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[1][0]=r[0];out[1][1]=r[1];out[1][2]=r[2];out[1][3]=r[3];goto L466;
}
L466:if(++steps>0x40000)return;{
const V &as=src(2,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[2][0]=r[0];out[2][1]=r[1];out[2][2]=r[2];out[2][3]=r[3];goto L467;
}
L467:if(++steps>0x40000)return;{
const V &as=src(3,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[3][0]=r[0];out[3][1]=r[1];out[3][2]=r[2];out[3][3]=r[3];goto L468;
}
L468:if(++steps>0x40000)return;{
const V &as=src(4,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L469;
}
L469:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[1],as[1]}};
const V &vs=src(5,0); V v={{vs[2],vs[3],vs[3],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L470;
}
L470:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[4][0]=r[0];out[4][1]=r[1];out[4][2]=r[2];out[4][3]=r[3];goto L471;
}
L471:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[5][0]=r[0];out[5][1]=r[1];out[5][2]=r[2];out[5][3]=r[3];goto L472;
}
L472:if(++steps>0x40000)return;{
if(emit)out=emit(emitter,out,2927624192u);goto L473;
}
L473:if(++steps>0x40000)return;{
if(emit)out=emit(emitter,out,2818572288u);goto L474;
}
L474:if(++steps>0x40000)return;{
const V &as=src(0,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L475;
}
L475:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(6,0); V v={{-vs[0],-vs[1],-vs[2],-vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L476;
}
L476:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[0][0]=r[0];out[0][1]=r[1];out[0][2]=r[2];out[0][3]=r[3];goto L477;
}
L477:if(++steps>0x40000)return;{
const V &as=src(1,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[1][0]=r[0];out[1][1]=r[1];out[1][2]=r[2];out[1][3]=r[3];goto L478;
}
L478:if(++steps>0x40000)return;{
const V &as=src(2,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[2][0]=r[0];out[2][1]=r[1];out[2][2]=r[2];out[2][3]=r[3];goto L479;
}
L479:if(++steps>0x40000)return;{
const V &as=src(3,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[3][0]=r[0];out[3][1]=r[1];out[3][2]=r[2];out[3][3]=r[3];goto L480;
}
L480:if(++steps>0x40000)return;{
const V &as=src(4,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[4][0]=r[0];out[4][1]=r[1];out[4][2]=r[2];out[4][3]=r[3];goto L481;
}
L481:if(++steps>0x40000)return;{
const V &as=src(4,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[5][0]=r[0];out[5][1]=r[1];out[5][2]=r[2];out[5][3]=r[3];goto L482;
}
L482:if(++steps>0x40000)return;{
if(emit)out=emit(emitter,out,2898264064u);goto L483;
}
L483:if(++steps>0x40000)return;{
if(emit)out=emit(emitter,out,2818572288u);goto L484;
}
L484:if(++steps>0x40000)return;{
return;}
}
