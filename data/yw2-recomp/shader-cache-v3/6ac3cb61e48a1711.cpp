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
int sp=0; uint32_t pc=0; int steps=0;
auto src=[&](uint32_t reg,int32_t offset)->const V& {
if(reg<16)return in[reg]; if(reg<32)return tmp[reg-16];
if(offset<-128||offset>127)offset=0; int32_t i=(int32_t(reg-32)+offset)&127; return i<96?f[i]:ones; };
auto push=[&](F v){if(sp<16)stack[sp++]=v;};
dispatch:
while(sp>0&&pc==stack[sp-1].final_pc) {
F &v=stack[sp-1]; if(v.loop) {addr[2]+=v.increment; if(v.repeat--==0){pc=v.return_pc;sp--;}else pc=v.loop_pc;}
else {pc=v.return_pc;sp--;}}
switch(pc) {
case 0:goto L0;
case 1:goto L1;
case 2:goto L2;
case 3:goto L3;
case 4:goto L4;
case 5:goto L5;
case 6:goto L6;
case 7:goto L7;
case 8:goto L8;
case 9:goto L9;
case 10:goto L10;
case 11:goto L11;
case 12:goto L12;
case 13:goto L13;
case 14:goto L14;
case 15:goto L15;
case 16:goto L16;
case 17:goto L17;
case 18:goto L18;
case 19:goto L19;
case 20:goto L20;
case 21:goto L21;
case 22:goto L22;
case 23:goto L23;
case 24:goto L24;
case 25:goto L25;
case 26:goto L26;
case 27:goto L27;
case 28:goto L28;
case 29:goto L29;
case 30:goto L30;
case 31:goto L31;
case 32:goto L32;
case 33:goto L33;
case 34:goto L34;
case 35:goto L35;
case 36:goto L36;
case 37:goto L37;
case 38:goto L38;
case 39:goto L39;
case 40:goto L40;
case 41:goto L41;
case 42:goto L42;
case 43:goto L43;
case 44:goto L44;
case 45:goto L45;
case 46:goto L46;
case 47:goto L47;
case 48:goto L48;
case 49:goto L49;
case 50:goto L50;
case 51:goto L51;
case 52:goto L52;
case 53:goto L53;
case 54:goto L54;
case 55:goto L55;
case 56:goto L56;
case 57:goto L57;
case 58:goto L58;
case 59:goto L59;
case 60:goto L60;
case 61:goto L61;
case 62:goto L62;
case 63:goto L63;
case 64:goto L64;
case 65:goto L65;
case 66:goto L66;
case 67:goto L67;
case 68:goto L68;
case 69:goto L69;
case 70:goto L70;
case 71:goto L71;
case 72:goto L72;
case 73:goto L73;
case 74:goto L74;
case 75:goto L75;
case 76:goto L76;
case 77:goto L77;
case 78:goto L78;
case 79:goto L79;
case 80:goto L80;
case 81:goto L81;
case 82:goto L82;
case 83:goto L83;
case 84:goto L84;
case 85:goto L85;
case 86:goto L86;
case 87:goto L87;
case 88:goto L88;
case 89:goto L89;
case 90:goto L90;
case 91:goto L91;
case 92:goto L92;
case 93:goto L93;
case 94:goto L94;
case 95:goto L95;
case 96:goto L96;
case 97:goto L97;
case 98:goto L98;
case 99:goto L99;
case 100:goto L100;
case 101:goto L101;
case 102:goto L102;
case 103:goto L103;
case 104:goto L104;
case 105:goto L105;
case 106:goto L106;
case 107:goto L107;
case 108:goto L108;
case 109:goto L109;
case 110:goto L110;
case 111:goto L111;
case 112:goto L112;
case 113:goto L113;
case 114:goto L114;
case 115:goto L115;
case 116:goto L116;
case 117:goto L117;
case 118:goto L118;
case 119:goto L119;
case 120:goto L120;
case 121:goto L121;
case 122:goto L122;
case 123:goto L123;
case 124:goto L124;
case 125:goto L125;
case 126:goto L126;
case 127:goto L127;
case 128:goto L128;
case 129:goto L129;
case 130:goto L130;
case 131:goto L131;
case 132:goto L132;
case 133:goto L133;
case 134:goto L134;
case 135:goto L135;
case 136:goto L136;
case 137:goto L137;
case 138:goto L138;
case 139:goto L139;
case 140:goto L140;
case 141:goto L141;
case 142:goto L142;
case 143:goto L143;
case 144:goto L144;
case 145:goto L145;
case 146:goto L146;
case 147:goto L147;
case 148:goto L148;
case 149:goto L149;
case 150:goto L150;
case 151:goto L151;
case 152:goto L152;
case 153:goto L153;
case 154:goto L154;
case 155:goto L155;
case 156:goto L156;
case 157:goto L157;
case 158:goto L158;
case 159:goto L159;
case 160:goto L160;
case 161:goto L161;
case 162:goto L162;
case 163:goto L163;
case 164:goto L164;
case 165:goto L165;
case 166:goto L166;
case 167:goto L167;
case 168:goto L168;
case 169:goto L169;
case 170:goto L170;
case 171:goto L171;
case 172:goto L172;
case 173:goto L173;
case 174:goto L174;
case 175:goto L175;
case 176:goto L176;
case 177:goto L177;
case 178:goto L178;
case 179:goto L179;
case 180:goto L180;
case 181:goto L181;
case 182:goto L182;
case 183:goto L183;
case 184:goto L184;
default:return;}
L0:if(++steps>0x40000)return;{
const V &as=src(0,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L1;
}
L1:if(++steps>0x40000)return;{
const V &as=src(1,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L2;
}
L2:if(++steps>0x40000)return;{
const V &as=src(126,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(6,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[3][0]=r[0];tmp[3][1]=r[1];tmp[3][2]=r[2];tmp[3][3]=r[3];goto L3;
}
L3:if(++steps>0x40000)return;{
const V &as=src(0,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[2][0]=r[0];tmp[2][1]=r[1];tmp[2][2]=r[2];tmp[2][3]=r[3];goto L4;
}
L4:if(++steps>0x40000)return;{
const V &as=src(1,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[4][0]=r[0];tmp[4][1]=r[1];tmp[4][2]=r[2];tmp[4][3]=r[3];goto L5;
}
L5:if(++steps>0x40000)return;{
if((((b>>5)&1)==0)){pc=41;goto dispatch;}goto L6;
}
L6:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
addr[0]=int32_t(a[0]);addr[1]=int32_t(a[1]);goto L7;
}
L7:if(++steps>0x40000)return;{
const V &as=src(44,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[5][0]=r[0];goto L8;
}
L8:if(++steps>0x40000)return;{
const V &as=src(45,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[5][1]=r[1];goto L9;
}
L9:if(++steps>0x40000)return;{
const V &as=src(46,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[5][2]=r[2];goto L10;
}
L10:if(++steps>0x40000)return;{
const V &as=src(44,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][0]=r[0];goto L11;
}
L11:if(++steps>0x40000)return;{
const V &as=src(45,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][1]=r[1];goto L12;
}
L12:if(++steps>0x40000)return;{
const V &as=src(46,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][2]=r[2];goto L13;
}
L13:if(++steps>0x40000)return;{
const V &as=src(21,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L14;
}
L14:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];goto L15;
}
L15:if(++steps>0x40000)return;{
if((((b>>8)&1)==0)){pc=41;goto dispatch;}goto L16;
}
L16:if(++steps>0x40000)return;{
const V &as=src(44,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[7][0]=r[0];goto L17;
}
L17:if(++steps>0x40000)return;{
const V &as=src(45,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[7][1]=r[1];goto L18;
}
L18:if(++steps>0x40000)return;{
const V &as=src(46,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[7][2]=r[2];goto L19;
}
L19:if(++steps>0x40000)return;{
const V &as=src(44,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[8][0]=r[0];goto L20;
}
L20:if(++steps>0x40000)return;{
const V &as=src(45,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[8][1]=r[1];goto L21;
}
L21:if(++steps>0x40000)return;{
const V &as=src(46,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[8][2]=r[2];goto L22;
}
L22:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[2],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
addr[0]=int32_t(a[0]);addr[1]=int32_t(a[1]);goto L23;
}
L23:if(++steps>0x40000)return;{
const V &as=src(44,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[9][0]=r[0];goto L24;
}
L24:if(++steps>0x40000)return;{
const V &as=src(45,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[9][1]=r[1];goto L25;
}
L25:if(++steps>0x40000)return;{
const V &as=src(46,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[9][2]=r[2];goto L26;
}
L26:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(16,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L27;
}
L27:if(++steps>0x40000)return;{
const V &as=src(44,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[10][0]=r[0];goto L28;
}
L28:if(++steps>0x40000)return;{
const V &as=src(45,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[10][1]=r[1];goto L29;
}
L29:if(++steps>0x40000)return;{
const V &as=src(46,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[10][2]=r[2];goto L30;
}
L30:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(17,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];goto L31;
}
L31:if(++steps>0x40000)return;{
const V &as=src(44,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[11][0]=r[0];goto L32;
}
L32:if(++steps>0x40000)return;{
const V &as=src(45,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[11][1]=r[1];goto L33;
}
L33:if(++steps>0x40000)return;{
const V &as=src(46,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[11][2]=r[2];goto L34;
}
L34:if(++steps>0x40000)return;{
const V &as=src(25,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
const V &cs=src(16,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L35;
}
L35:if(++steps>0x40000)return;{
const V &as=src(44,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[12][0]=r[0];goto L36;
}
L36:if(++steps>0x40000)return;{
const V &as=src(45,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[12][1]=r[1];goto L37;
}
L37:if(++steps>0x40000)return;{
const V &as=src(46,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[12][2]=r[2];goto L38;
}
L38:if(++steps>0x40000)return;{
const V &as=src(26,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
const V &cs=src(17,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];goto L39;
}
L39:if(++steps>0x40000)return;{
const V &as=src(27,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
const V &cs=src(16,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L40;
}
L40:if(++steps>0x40000)return;{
const V &as=src(28,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
const V &cs=src(17,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];goto L41;
}
L41:if(++steps>0x40000)return;{
if(((b>>6)&1)){push({53,65,0,0,0,false});pc=42;}else{push({65,65,0,0,0,false});pc=53;}goto dispatch;}
L42:if(++steps>0x40000)return;{
const V &as=src(32,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][0]=r[0];goto L43;
}
L43:if(++steps>0x40000)return;{
const V &as=src(33,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][1]=r[1];goto L44;
}
L44:if(++steps>0x40000)return;{
const V &as=src(34,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][2]=r[2];goto L45;
}
L45:if(++steps>0x40000)return;{
const V &as=src(32,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][0]=r[0];goto L46;
}
L46:if(++steps>0x40000)return;{
const V &as=src(33,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][1]=r[1];goto L47;
}
L47:if(++steps>0x40000)return;{
const V &as=src(34,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][2]=r[2];goto L48;
}
L48:if(++steps>0x40000)return;{
const V &as=src(109,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[4][0]=r[0];goto L49;
}
L49:if(++steps>0x40000)return;{
const V &as=src(112,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(20,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[5][0]=r[0];goto L50;
}
L50:if(++steps>0x40000)return;{
const V &as=src(18,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L51;
}
L51:if(++steps>0x40000)return;{
const V &as=src(18,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(21,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];goto L52;
}
L52:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];pc=53;goto dispatch;
}
L53:if(++steps>0x40000)return;{
const V &as=src(32,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][0]=r[0];goto L54;
}
L54:if(++steps>0x40000)return;{
const V &as=src(33,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][1]=r[1];goto L55;
}
L55:if(++steps>0x40000)return;{
const V &as=src(34,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][2]=r[2];goto L56;
}
L56:if(++steps>0x40000)return;{
const V &as=src(32,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][0]=r[0];goto L57;
}
L57:if(++steps>0x40000)return;{
const V &as=src(33,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][1]=r[1];goto L58;
}
L58:if(++steps>0x40000)return;{
const V &as=src(34,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][2]=r[2];goto L59;
}
L59:if(++steps>0x40000)return;{
const V &as=src(122,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(19,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[1][0]=r[0];goto L60;
}
L60:if(++steps>0x40000)return;{
const V &as=src(123,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(19,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[1][1]=r[1];goto L61;
}
L61:if(++steps>0x40000)return;{
const V &as=src(124,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(19,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[1][2]=r[2];goto L62;
}
L62:if(++steps>0x40000)return;{
const V &as=src(122,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[0][0]=r[0];goto L63;
}
L63:if(++steps>0x40000)return;{
const V &as=src(123,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[0][1]=r[1];goto L64;
}
L64:if(++steps>0x40000)return;{
const V &as=src(124,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[0][2]=r[2];pc=65;goto dispatch;
}
L65:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[2][0]=r[0];tmp[2][1]=r[1];tmp[2][2]=r[2];tmp[2][3]=r[3];goto L66;
}
L66:if(++steps>0x40000)return;{
const V &as=src(18,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[4][0]=r[0];tmp[4][1]=r[1];tmp[4][2]=r[2];tmp[4][3]=r[3];goto L67;
}
L67:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(20,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[5][0]=r[0];tmp[5][1]=r[1];tmp[5][2]=r[2];tmp[5][3]=r[3];goto L68;
}
L68:if(++steps>0x40000)return;{
const V &as=src(21,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(20,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[5][0]=r[0];tmp[5][1]=r[1];tmp[5][2]=r[2];tmp[5][3]=r[3];goto L69;
}
L69:if(++steps>0x40000)return;{
const V &as=src(21,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[4][0]=r[0];tmp[4][1]=r[1];tmp[4][2]=r[2];tmp[4][3]=r[3];goto L70;
}
L70:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(20,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];goto L71;
}
L71:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{-as[0],-as[1],-as[2],-as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[1][0]=r[0];out[1][1]=r[1];out[1][2]=r[2];out[1][3]=r[3];goto L72;
}
L72:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[14][0]=r[0];tmp[14][1]=r[1];tmp[14][2]=r[2];tmp[14][3]=r[3];goto L73;
}
L73:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[3],as[3],as[3],as[3]}};
const V &vs=src(17,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[2][0]=r[0];tmp[2][1]=r[1];tmp[2][2]=r[2];tmp[2][3]=r[3];goto L74;
}
L74:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[2][0]=r[0];tmp[2][1]=r[1];tmp[2][2]=r[2];tmp[2][3]=r[3];goto L75;
}
L75:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(18,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
cond[0]=a[0]<v[0];cond[1]=a[1]<v[1];goto L76;
}
L76:if(++steps>0x40000)return;{
if((cond[0]==1)){push({82,83,0,0,0,false});pc=77;}else{push({83,83,0,0,0,false});pc=82;}goto dispatch;}
L77:if(++steps>0x40000)return;{
const V &as=src(18,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[2][0]=r[0];tmp[2][1]=r[1];tmp[2][2]=r[2];tmp[2][3]=r[3];goto L78;
}
L78:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[3][0]=r[0];tmp[3][1]=r[1];tmp[3][2]=r[2];tmp[3][3]=r[3];goto L79;
}
L79:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);out[2][0]=r[0];out[2][1]=r[1];goto L80;
}
L80:if(++steps>0x40000)return;{
const V &as=src(18,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
float d=1.0f/a[0];r={{d,d,d,d}};out[2][2]=r[2];goto L81;
}
L81:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[2][3]=r[3];pc=82;goto dispatch;
}
L82:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[3],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[2][0]=r[0];out[2][1]=r[1];out[2][2]=r[2];out[2][3]=r[3];pc=83;goto dispatch;
}
L83:if(++steps>0x40000)return;{
if(((b>>6)&1)){push({92,148,0,0,0,false});pc=84;}else{push({148,148,0,0,0,false});pc=92;}goto dispatch;}
L84:if(++steps>0x40000)return;{
const V &as=src(104,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][0]=r[0];goto L85;
}
L85:if(++steps>0x40000)return;{
const V &as=src(105,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][1]=r[1];goto L86;
}
L86:if(++steps>0x40000)return;{
const V &as=src(106,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][2]=r[2];goto L87;
}
L87:if(++steps>0x40000)return;{
const V &as=src(107,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][3]=r[3];goto L88;
}
L88:if(++steps>0x40000)return;{
const V &as=src(104,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][0]=r[0];goto L89;
}
L89:if(++steps>0x40000)return;{
const V &as=src(105,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][1]=r[1];goto L90;
}
L90:if(++steps>0x40000)return;{
const V &as=src(106,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][2]=r[2];goto L91;
}
L91:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[7][0]=r[0];out[7][1]=r[1];out[7][2]=r[2];out[7][3]=r[3];pc=92;goto dispatch;
}
L92:if(++steps>0x40000)return;{
const V &as=src(118,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][0]=r[0];goto L93;
}
L93:if(++steps>0x40000)return;{
const V &as=src(119,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][1]=r[1];goto L94;
}
L94:if(++steps>0x40000)return;{
const V &as=src(120,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][2]=r[2];goto L95;
}
L95:if(++steps>0x40000)return;{
const V &as=src(121,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[2][3]=r[3];goto L96;
}
L96:if(++steps>0x40000)return;{
const V &as=src(110,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[5][0]=r[0];tmp[5][1]=r[1];tmp[5][2]=r[2];tmp[5][3]=r[3];goto L97;
}
L97:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(21,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
cond[0]=a[0]<v[0];cond[1]=a[1]<v[1];goto L98;
}
L98:if(++steps>0x40000)return;{
if(((cond[0]==1)||(cond[1]==1))){push({144,147,0,0,0,false});pc=99;}else{push({147,147,0,0,0,false});pc=144;}goto dispatch;}
L99:if(++steps>0x40000)return;{
const V &as=src(126,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(6,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L100;
}
L100:if(++steps>0x40000)return;{
const V &as=src(8,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[15][0]=r[0];tmp[15][1]=r[1];tmp[15][2]=r[2];tmp[15][3]=r[3];goto L101;
}
L101:if(++steps>0x40000)return;{
if(((b>>5)&1)){push({121,121,0,0,0,false});pc=102;}else{push({121,121,0,0,0,false});pc=121;}goto dispatch;}
L102:if(++steps>0x40000)return;{
const V &as=src(31,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[5][0]=r[0];tmp[5][1]=r[1];tmp[5][2]=r[2];tmp[5][3]=r[3];goto L103;
}
L103:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
addr[0]=int32_t(a[0]);addr[1]=int32_t(a[1]);goto L104;
}
L104:if(++steps>0x40000)return;{
const V &as=src(44,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][0]=r[0];goto L105;
}
L105:if(++steps>0x40000)return;{
const V &as=src(45,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][1]=r[1];goto L106;
}
L106:if(++steps>0x40000)return;{
const V &as=src(46,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][2]=r[2];goto L107;
}
L107:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[15][0]=r[0];tmp[15][1]=r[1];tmp[15][2]=r[2];goto L108;
}
L108:if(++steps>0x40000)return;{
const V &as=src(44,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][0]=r[0];goto L109;
}
L109:if(++steps>0x40000)return;{
const V &as=src(45,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][1]=r[1];goto L110;
}
L110:if(++steps>0x40000)return;{
const V &as=src(46,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][2]=r[2];goto L111;
}
L111:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(31,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[15][0]=r[0];tmp[15][1]=r[1];tmp[15][2]=r[2];goto L112;
}
L112:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[2],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
addr[0]=int32_t(a[0]);addr[1]=int32_t(a[1]);goto L113;
}
L113:if(++steps>0x40000)return;{
const V &as=src(44,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][0]=r[0];goto L114;
}
L114:if(++steps>0x40000)return;{
const V &as=src(45,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][1]=r[1];goto L115;
}
L115:if(++steps>0x40000)return;{
const V &as=src(46,addr[0]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][2]=r[2];goto L116;
}
L116:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
const V &cs=src(31,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[15][0]=r[0];tmp[15][1]=r[1];tmp[15][2]=r[2];goto L117;
}
L117:if(++steps>0x40000)return;{
const V &as=src(44,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][0]=r[0];goto L118;
}
L118:if(++steps>0x40000)return;{
const V &as=src(45,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][1]=r[1];goto L119;
}
L119:if(++steps>0x40000)return;{
const V &as=src(46,addr[1]); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[4][2]=r[2];goto L120;
}
L120:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(7,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
const V &cs=src(31,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[15][0]=r[0];tmp[15][1]=r[1];tmp[15][2]=r[2];pc=121;goto dispatch;
}
L121:if(++steps>0x40000)return;{
const V &as=src(32,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][0]=r[0];goto L122;
}
L122:if(++steps>0x40000)return;{
const V &as=src(33,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][1]=r[1];goto L123;
}
L123:if(++steps>0x40000)return;{
const V &as=src(34,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][2]=r[2];goto L124;
}
L124:if(++steps>0x40000)return;{
const V &as=src(122,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(22,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[15][0]=r[0];goto L125;
}
L125:if(++steps>0x40000)return;{
const V &as=src(123,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(22,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[15][1]=r[1];goto L126;
}
L126:if(++steps>0x40000)return;{
const V &as=src(124,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(22,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[15][2]=r[2];goto L127;
}
L127:if(++steps>0x40000)return;{
const V &as=src(118,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][0]=r[0];goto L128;
}
L128:if(++steps>0x40000)return;{
const V &as=src(119,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][1]=r[1];goto L129;
}
L129:if(++steps>0x40000)return;{
const V &as=src(120,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][2]=r[2];goto L130;
}
L130:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L131;
}
L131:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[6][2]=r[2];tmp[6][3]=r[3];goto L132;
}
L132:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(22,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[4][0]=r[0];tmp[4][1]=r[1];tmp[4][2]=r[2];tmp[4][3]=r[3];goto L133;
}
L133:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(20,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[5][0]=r[0];tmp[5][1]=r[1];tmp[5][2]=r[2];tmp[5][3]=r[3];goto L134;
}
L134:if(++steps>0x40000)return;{
const V &as=src(21,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[4][0]=r[0];tmp[4][1]=r[1];tmp[4][2]=r[2];tmp[4][3]=r[3];goto L135;
}
L135:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(20,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[3][0]=r[0];goto L136;
}
L136:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(20,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[3][1]=r[1];goto L137;
}
L137:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[3][2]=r[2];tmp[3][3]=r[3];goto L138;
}
L138:if(++steps>0x40000)return;{
const V &as=src(18,0); V a={{as[3],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
float d=1.0f/a[0];r={{d,d,d,d}};tmp[4][0]=r[0];tmp[4][1]=r[1];tmp[4][2]=r[2];tmp[4][3]=r[3];goto L139;
}
L139:if(++steps>0x40000)return;{
const V &as=src(127,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(20,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]>v[k]?a[k]:v[k];tmp[4][0]=r[0];tmp[4][1]=r[1];tmp[4][2]=r[2];tmp[4][3]=r[3];goto L140;
}
L140:if(++steps>0x40000)return;{
const V &as=src(18,0); V a={{-as[2],-as[2],-as[2],-as[2]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L141;
}
L141:if(++steps>0x40000)return;{
const V &as=src(110,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(22,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];tmp[7][3]=r[3];goto L142;
}
L142:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(23,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[8][0]=r[0];tmp[8][1]=r[1];goto L143;
}
L143:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{as[0],as[1],as[1],as[1]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[2][0]=r[0];tmp[2][1]=r[1];pc=144;goto dispatch;
}
L144:if(++steps>0x40000)return;{
const V &as=src(118,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][0]=r[0];goto L145;
}
L145:if(++steps>0x40000)return;{
const V &as=src(119,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][1]=r[1];goto L146;
}
L146:if(++steps>0x40000)return;{
const V &as=src(120,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[3][2]=r[2];pc=147;goto dispatch;
}
L147:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[7][0]=r[0];out[7][1]=r[1];out[7][2]=r[2];out[7][3]=r[3];pc=148;goto dispatch;
}
L148:if(++steps>0x40000)return;{
const V &as=src(18,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[0][0]=r[0];out[0][1]=r[1];out[0][2]=r[2];out[0][3]=r[3];goto L149;
}
L149:if(++steps>0x40000)return;{
const V &as=src(4,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[3][0]=r[0];tmp[3][1]=r[1];tmp[3][2]=r[2];tmp[3][3]=r[3];goto L150;
}
L150:if(++steps>0x40000)return;{
const V &as=src(5,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[4][0]=r[0];tmp[4][1]=r[1];tmp[4][2]=r[2];tmp[4][3]=r[3];goto L151;
}
L151:if(++steps>0x40000)return;{
if(((b>>7)&1)){push({172,183,0,0,0,false});pc=152;}else{push({183,183,0,0,0,false});pc=172;}goto dispatch;}
L152:if(++steps>0x40000)return;{
if(((b>>9)&1)){push({156,157,0,0,0,false});pc=153;}else{push({157,157,0,0,0,false});pc=156;}goto dispatch;}
L153:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(30,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[5][0]=r[0];tmp[5][1]=r[1];goto L154;
}
L154:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[2][0]=r[0];tmp[2][1]=r[1];goto L155;
}
L155:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
tmp[2][2]=r[2];pc=156;goto dispatch;
}
L156:if(++steps>0x40000)return;{
const V &as=src(3,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[2][0]=r[0];tmp[2][1]=r[1];tmp[2][2]=r[2];pc=157;goto dispatch;
}
L157:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[3][2]=r[2];tmp[3][3]=r[3];goto L158;
}
L158:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[4][2]=r[2];tmp[4][3]=r[3];goto L159;
}
L159:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[3],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[2][3]=r[3];goto L160;
}
L160:if(++steps>0x40000)return;{
const V &as=src(38,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(19,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[5][0]=r[0];goto L161;
}
L161:if(++steps>0x40000)return;{
const V &as=src(39,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(19,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[5][1]=r[1];goto L162;
}
L162:if(++steps>0x40000)return;{
const V &as=src(40,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(19,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[5][2]=r[2];goto L163;
}
L163:if(++steps>0x40000)return;{
const V &as=src(41,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[6][0]=r[0];goto L164;
}
L164:if(++steps>0x40000)return;{
const V &as=src(42,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[6][1]=r[1];goto L165;
}
L165:if(++steps>0x40000)return;{
const V &as=src(43,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(20,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[6][2]=r[2];goto L166;
}
L166:if(++steps>0x40000)return;{
const V &as=src(35,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[4][0]=r[0];goto L167;
}
L167:if(++steps>0x40000)return;{
const V &as=src(36,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[4][1]=r[1];goto L168;
}
L168:if(++steps>0x40000)return;{
const V &as=src(37,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[4][2]=r[2];goto L169;
}
L169:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[3],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[5][3]=r[3];goto L170;
}
L170:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[3],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[6][3]=r[3];goto L171;
}
L171:if(++steps>0x40000)return;{
const V &as=src(18,0); V a={{as[3],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[4][3]=r[3];pc=172;goto dispatch;
}
L172:if(++steps>0x40000)return;{
if(((b>>9)&1)){push({176,177,0,0,0,false});pc=173;}else{push({177,177,0,0,0,false});pc=176;}goto dispatch;}
L173:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(30,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[5][0]=r[0];tmp[5][1]=r[1];goto L174;
}
L174:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(21,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[2][0]=r[0];tmp[2][1]=r[1];goto L175;
}
L175:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
tmp[2][2]=r[2];pc=176;goto dispatch;
}
L176:if(++steps>0x40000)return;{
const V &as=src(3,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[2][0]=r[0];tmp[2][1]=r[1];tmp[2][2]=r[2];pc=177;goto dispatch;
}
L177:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[3],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[2][3]=r[3];goto L178;
}
L178:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[3][2]=r[2];tmp[3][3]=r[3];goto L179;
}
L179:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[4][2]=r[2];tmp[4][3]=r[3];goto L180;
}
L180:if(++steps>0x40000)return;{
const V &as=src(18,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[4][0]=r[0];out[4][1]=r[1];out[4][2]=r[2];out[4][3]=r[3];goto L181;
}
L181:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[5][0]=r[0];out[5][1]=r[1];out[5][2]=r[2];out[5][3]=r[3];goto L182;
}
L182:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[6][0]=r[0];out[6][1]=r[1];out[6][2]=r[2];out[6][3]=r[3];pc=183;goto dispatch;
}
L183:if(++steps>0x40000)return;{
const V &as=src(111,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(2,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);out[3][0]=r[0];out[3][1]=r[1];out[3][2]=r[2];out[3][3]=r[3];goto L184;
}
L184:if(++steps>0x40000)return;{
return;}
}
