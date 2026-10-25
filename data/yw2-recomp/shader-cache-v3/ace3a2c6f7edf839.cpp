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
int sp=0; uint32_t pc=186; int steps=0;
auto src=[&](uint32_t reg,int32_t offset)->const V& {
if(reg<16)return in[reg]; if(reg<32)return tmp[reg-16];
if(offset<-128||offset>127)offset=0; int32_t i=(int32_t(reg-32)+offset)&127; return i<96?f[i]:ones; };
auto push=[&](F v){if(sp<16)stack[sp++]=v;};
dispatch:
while(sp>0&&pc==stack[sp-1].final_pc) {
F &v=stack[sp-1]; if(v.loop) {addr[2]+=v.increment; if(v.repeat--==0){pc=v.return_pc;sp--;}else pc=v.loop_pc;}
else {pc=v.return_pc;sp--;}}
switch(pc) {
case 186:goto L186;
case 187:goto L187;
case 188:goto L188;
case 189:goto L189;
case 190:goto L190;
case 191:goto L191;
case 192:goto L192;
case 193:goto L193;
case 194:goto L194;
case 195:goto L195;
case 196:goto L196;
case 197:goto L197;
case 198:goto L198;
case 199:goto L199;
case 200:goto L200;
case 201:goto L201;
case 202:goto L202;
case 203:goto L203;
case 204:goto L204;
case 205:goto L205;
case 206:goto L206;
case 207:goto L207;
case 208:goto L208;
case 209:goto L209;
case 210:goto L210;
case 211:goto L211;
case 212:goto L212;
case 213:goto L213;
case 214:goto L214;
case 215:goto L215;
case 216:goto L216;
case 217:goto L217;
case 218:goto L218;
case 219:goto L219;
case 220:goto L220;
case 221:goto L221;
case 222:goto L222;
case 223:goto L223;
case 224:goto L224;
case 225:goto L225;
case 226:goto L226;
case 227:goto L227;
case 228:goto L228;
case 229:goto L229;
case 230:goto L230;
case 231:goto L231;
case 232:goto L232;
case 233:goto L233;
case 234:goto L234;
case 235:goto L235;
case 236:goto L236;
case 237:goto L237;
case 238:goto L238;
case 239:goto L239;
case 240:goto L240;
case 241:goto L241;
case 242:goto L242;
case 243:goto L243;
case 244:goto L244;
case 245:goto L245;
case 246:goto L246;
case 247:goto L247;
case 248:goto L248;
case 249:goto L249;
case 250:goto L250;
case 251:goto L251;
case 252:goto L252;
case 253:goto L253;
case 254:goto L254;
case 255:goto L255;
case 256:goto L256;
case 257:goto L257;
case 258:goto L258;
case 259:goto L259;
case 260:goto L260;
case 261:goto L261;
case 262:goto L262;
case 263:goto L263;
case 264:goto L264;
case 265:goto L265;
case 266:goto L266;
case 267:goto L267;
case 268:goto L268;
case 269:goto L269;
case 270:goto L270;
case 271:goto L271;
case 272:goto L272;
case 273:goto L273;
case 274:goto L274;
case 275:goto L275;
case 276:goto L276;
case 277:goto L277;
case 278:goto L278;
case 279:goto L279;
case 280:goto L280;
case 281:goto L281;
case 282:goto L282;
case 283:goto L283;
case 284:goto L284;
case 285:goto L285;
case 286:goto L286;
case 287:goto L287;
case 288:goto L288;
case 289:goto L289;
case 290:goto L290;
case 291:goto L291;
case 292:goto L292;
case 293:goto L293;
case 294:goto L294;
case 295:goto L295;
case 296:goto L296;
case 297:goto L297;
case 298:goto L298;
case 299:goto L299;
case 300:goto L300;
case 301:goto L301;
case 302:goto L302;
case 303:goto L303;
case 304:goto L304;
case 305:goto L305;
case 306:goto L306;
case 307:goto L307;
case 308:goto L308;
case 309:goto L309;
case 310:goto L310;
case 311:goto L311;
case 312:goto L312;
case 313:goto L313;
case 314:goto L314;
case 315:goto L315;
case 316:goto L316;
case 317:goto L317;
case 318:goto L318;
case 319:goto L319;
case 320:goto L320;
case 321:goto L321;
case 322:goto L322;
case 323:goto L323;
case 324:goto L324;
case 325:goto L325;
case 326:goto L326;
case 327:goto L327;
case 328:goto L328;
case 329:goto L329;
case 330:goto L330;
case 331:goto L331;
case 332:goto L332;
case 333:goto L333;
case 334:goto L334;
case 335:goto L335;
case 336:goto L336;
case 337:goto L337;
case 338:goto L338;
case 339:goto L339;
case 340:goto L340;
case 341:goto L341;
case 342:goto L342;
case 343:goto L343;
case 344:goto L344;
case 345:goto L345;
case 346:goto L346;
case 347:goto L347;
case 348:goto L348;
case 349:goto L349;
case 350:goto L350;
case 351:goto L351;
case 352:goto L352;
case 353:goto L353;
case 354:goto L354;
case 355:goto L355;
case 356:goto L356;
case 357:goto L357;
case 358:goto L358;
case 359:goto L359;
case 360:goto L360;
case 361:goto L361;
case 362:goto L362;
case 363:goto L363;
case 364:goto L364;
case 365:goto L365;
case 366:goto L366;
case 367:goto L367;
case 368:goto L368;
case 369:goto L369;
case 370:goto L370;
case 371:goto L371;
case 372:goto L372;
case 373:goto L373;
case 374:goto L374;
case 375:goto L375;
case 376:goto L376;
case 377:goto L377;
case 378:goto L378;
case 379:goto L379;
case 380:goto L380;
case 381:goto L381;
case 382:goto L382;
case 383:goto L383;
case 384:goto L384;
case 385:goto L385;
case 386:goto L386;
case 387:goto L387;
case 388:goto L388;
case 389:goto L389;
case 390:goto L390;
case 391:goto L391;
case 392:goto L392;
case 393:goto L393;
case 394:goto L394;
case 395:goto L395;
case 396:goto L396;
case 397:goto L397;
case 398:goto L398;
case 399:goto L399;
case 400:goto L400;
case 401:goto L401;
case 402:goto L402;
case 403:goto L403;
case 404:goto L404;
case 405:goto L405;
case 406:goto L406;
case 407:goto L407;
case 408:goto L408;
case 409:goto L409;
case 410:goto L410;
case 411:goto L411;
case 412:goto L412;
case 413:goto L413;
case 414:goto L414;
case 415:goto L415;
case 416:goto L416;
case 417:goto L417;
case 418:goto L418;
case 419:goto L419;
case 420:goto L420;
case 421:goto L421;
case 422:goto L422;
case 423:goto L423;
case 424:goto L424;
case 425:goto L425;
case 426:goto L426;
case 427:goto L427;
case 428:goto L428;
case 429:goto L429;
case 430:goto L430;
case 431:goto L431;
case 432:goto L432;
case 433:goto L433;
case 434:goto L434;
case 435:goto L435;
default:return;}
L186:if(++steps>0x40000)return;{
const V &as=src(2,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L187;
}
L187:if(++steps>0x40000)return;{
const V &as=src(71,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L188;
}
L188:if(++steps>0x40000)return;{
const V &as=src(116,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L189;
}
L189:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=std::floor(a[k]);tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L190;
}
L190:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{-vs[0],-vs[1],-vs[2],-vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[12][0]=r[0];tmp[12][1]=r[1];tmp[12][2]=r[2];tmp[12][3]=r[3];goto L191;
}
L191:if(++steps>0x40000)return;{
const V &as=src(1,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L192;
}
L192:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(8,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L193;
}
L193:if(++steps>0x40000)return;{
const V &as=src(70,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[13][0]=r[0];tmp[13][1]=r[1];tmp[13][2]=r[2];tmp[13][3]=r[3];goto L194;
}
L194:if(++steps>0x40000)return;{
if(((b>>1)&1)){push({236,236,0,0,0,false});pc=195;}else{push({236,236,0,0,0,false});pc=236;}goto dispatch;}
L195:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[9][0]=r[0];tmp[9][1]=r[1];tmp[9][2]=r[2];tmp[9][3]=r[3];goto L196;
}
L196:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[10][0]=r[0];tmp[10][1]=r[1];tmp[10][2]=r[2];tmp[10][3]=r[3];goto L197;
}
L197:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[11][0]=r[0];tmp[11][1]=r[1];tmp[11][2]=r[2];tmp[11][3]=r[3];goto L198;
}
L198:if(++steps>0x40000)return;{
const V &as=src(28,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(28,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[3][0]=r[0];tmp[3][1]=r[1];tmp[3][2]=r[2];tmp[3][3]=r[3];goto L199;
}
L199:if(++steps>0x40000)return;{
const V &as=src(115,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L200;
}
L200:if(++steps>0x40000)return;{
const V &as=src(114,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[2][0]=r[0];tmp[2][1]=r[1];tmp[2][2]=r[2];tmp[2][3]=r[3];goto L201;
}
L201:if(++steps>0x40000)return;{
const V &as=src(113,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[5][0]=r[0];tmp[5][1]=r[1];tmp[5][2]=r[2];tmp[5][3]=r[3];goto L202;
}
L202:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(17,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L203;
}
L203:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(18,0); V c={{cs[0],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L204;
}
L204:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(18,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L205;
}
L205:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(21,0); V c={{cs[0],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L206;
}
L206:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(21,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L207;
}
L207:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(28,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][1]=r[1];goto L208;
}
L208:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(16,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
const V &cs=src(125,0); V c={{cs[1],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];goto L209;
}
L209:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[4][0]=r[0];tmp[4][1]=r[1];goto L210;
}
L210:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(17,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L211;
}
L211:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(18,0); V c={{cs[0],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L212;
}
L212:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(18,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L213;
}
L213:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(21,0); V c={{cs[0],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L214;
}
L214:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(21,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L215;
}
L215:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(28,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][1]=r[1];goto L216;
}
L216:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(16,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
const V &cs=src(125,0); V c={{cs[1],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];goto L217;
}
L217:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[0],as[0],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[4][2]=r[2];tmp[4][3]=r[3];goto L218;
}
L218:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(17,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L219;
}
L219:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(18,0); V c={{cs[0],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L220;
}
L220:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(18,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L221;
}
L221:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(21,0); V c={{cs[0],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L222;
}
L222:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(21,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L223;
}
L223:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(28,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][1]=r[1];goto L224;
}
L224:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
const V &cs=src(125,0); V c={{cs[1],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];goto L225;
}
L225:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{-as[3],-as[3],-as[3],-as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[11][0]=r[0];goto L226;
}
L226:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(20,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[9][0]=r[0];goto L227;
}
L227:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(20,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[10][0]=r[0];goto L228;
}
L228:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(20,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[11][1]=r[1];goto L229;
}
L229:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(20,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[11][2]=r[2];goto L230;
}
L230:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[0],as[1],as[1],as[1]}};
const V &vs=src(16,0); V v={{vs[1],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[1][0]=r[0];tmp[1][1]=r[1];goto L231;
}
L231:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(20,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
const V &cs=src(17,0); V c={{-cs[0],-cs[0],-cs[0],-cs[0]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[9][1]=r[1];goto L232;
}
L232:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(20,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
const V &cs=src(17,0); V c={{-cs[1],-cs[1],-cs[1],-cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[10][2]=r[2];goto L233;
}
L233:if(++steps>0x40000)return;{
const V &as=src(20,0); V a={{as[1],as[0],as[0],as[0]}};
const V &vs=src(16,0); V v={{vs[1],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[1][0]=r[0];tmp[1][1]=r[1];goto L234;
}
L234:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(20,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
const V &cs=src(17,0); V c={{cs[0],cs[0],cs[0],cs[0]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[9][2]=r[2];goto L235;
}
L235:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(20,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
const V &cs=src(17,0); V c={{cs[1],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[10][1]=r[1];pc=236;goto dispatch;
}
L236:if(++steps>0x40000)return;{
if(((b>>3)&1)){push({259,368,0,0,0,false});pc=237;}else{push({368,368,0,0,0,false});pc=259;}goto dispatch;}
L237:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[6][1]=r[1];tmp[6][2]=r[2];goto L238;
}
L238:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[7][0]=r[0];tmp[7][2]=r[2];goto L239;
}
L239:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[6][0]=r[0];tmp[6][3]=r[3];goto L240;
}
L240:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[7][1]=r[1];tmp[7][3]=r[3];goto L241;
}
L241:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(29,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];goto L242;
}
L242:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(29,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];goto L243;
}
L243:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(25,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];goto L244;
}
L244:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(26,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][1]=r[1];goto L245;
}
L245:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(27,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][2]=r[2];goto L246;
}
L246:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L247;
}
L247:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(25,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[1][0]=r[0];goto L248;
}
L248:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(26,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[1][1]=r[1];goto L249;
}
L249:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(27,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[1][2]=r[2];goto L250;
}
L250:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];tmp[7][3]=r[3];goto L251;
}
L251:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L252;
}
L252:if(++steps>0x40000)return;{
const V &as=src(57,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][0]=r[0];goto L253;
}
L253:if(++steps>0x40000)return;{
const V &as=src(58,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][1]=r[1];goto L254;
}
L254:if(++steps>0x40000)return;{
const V &as=src(59,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][2]=r[2];goto L255;
}
L255:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L256;
}
L256:if(++steps>0x40000)return;{
const V &as=src(57,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[7][0]=r[0];goto L257;
}
L257:if(++steps>0x40000)return;{
const V &as=src(58,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[7][1]=r[1];goto L258;
}
L258:if(++steps>0x40000)return;{
const V &as=src(59,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[7][2]=r[2];pc=259;goto dispatch;
}
L259:if(++steps>0x40000)return;{
if(((b>>2)&1)){push({300,367,0,0,0,false});pc=260;}else{push({367,367,0,0,0,false});pc=300;}goto dispatch;}
L260:if(++steps>0x40000)return;{
const V &as=src(60,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[8][0]=r[0];goto L261;
}
L261:if(++steps>0x40000)return;{
const V &as=src(61,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[8][1]=r[1];goto L262;
}
L262:if(++steps>0x40000)return;{
const V &as=src(62,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
tmp[8][2]=r[2];goto L263;
}
L263:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(24,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L264;
}
L264:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L265;
}
L265:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[8][0]=r[0];tmp[8][1]=r[1];tmp[8][2]=r[2];tmp[8][3]=r[3];goto L266;
}
L266:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L267;
}
L267:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];tmp[7][3]=r[3];goto L268;
}
L268:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[6][0]=r[0];goto L269;
}
L269:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[7][1]=r[1];goto L270;
}
L270:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(25,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];goto L271;
}
L271:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(26,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][1]=r[1];goto L272;
}
L272:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(27,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][2]=r[2];goto L273;
}
L273:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L274;
}
L274:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(25,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[1][0]=r[0];goto L275;
}
L275:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(26,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[1][1]=r[1];goto L276;
}
L276:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(27,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[1][2]=r[2];goto L277;
}
L277:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];tmp[7][3]=r[3];goto L278;
}
L278:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[1],as[2],as[0],as[0]}};
const V &vs=src(24,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L279;
}
L279:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{-as[1],-as[2],-as[0],-as[0]}};
const V &vs=src(23,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
const V &cs=src(16,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L280;
}
L280:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[1],as[2],as[0],as[0]}};
const V &vs=src(23,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[8][0]=r[0];tmp[8][1]=r[1];tmp[8][2]=r[2];goto L281;
}
L281:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{-as[1],-as[2],-as[0],-as[0]}};
const V &vs=src(16,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
const V &cs=src(24,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[8][0]=r[0];tmp[8][1]=r[1];tmp[8][2]=r[2];goto L282;
}
L282:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(22,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L283;
}
L283:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[3][0]=r[0];tmp[3][1]=r[1];tmp[3][2]=r[2];tmp[3][3]=r[3];goto L284;
}
L284:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[1],as[2],as[0],as[0]}};
const V &vs=src(24,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];goto L285;
}
L285:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{-as[1],-as[2],-as[0],-as[0]}};
const V &vs=src(23,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
const V &cs=src(22,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];goto L286;
}
L286:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(22,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L287;
}
L287:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L288;
}
L288:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L289;
}
L289:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(19,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L290;
}
L290:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L291;
}
L291:if(++steps>0x40000)return;{
const V &as=src(57,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][0]=r[0];goto L292;
}
L292:if(++steps>0x40000)return;{
const V &as=src(58,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][1]=r[1];goto L293;
}
L293:if(++steps>0x40000)return;{
const V &as=src(59,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][2]=r[2];goto L294;
}
L294:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L295;
}
L295:if(++steps>0x40000)return;{
const V &as=src(57,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[7][0]=r[0];goto L296;
}
L296:if(++steps>0x40000)return;{
const V &as=src(58,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[7][1]=r[1];goto L297;
}
L297:if(++steps>0x40000)return;{
const V &as=src(59,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[7][2]=r[2];goto L298;
}
L298:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(29,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L299;
}
L299:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(29,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];tmp[7][3]=r[3];pc=300;goto dispatch;
}
L300:if(++steps>0x40000)return;{
if(((b>>4)&1)){push({315,333,0,0,0,false});pc=301;}else{push({333,333,0,0,0,false});pc=315;}goto dispatch;}
L301:if(++steps>0x40000)return;{
const V &as=src(60,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[8][0]=r[0];goto L302;
}
L302:if(++steps>0x40000)return;{
const V &as=src(61,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[8][1]=r[1];goto L303;
}
L303:if(++steps>0x40000)return;{
const V &as=src(62,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
tmp[8][2]=r[2];goto L304;
}
L304:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(24,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L305;
}
L305:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L306;
}
L306:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[8][0]=r[0];tmp[8][1]=r[1];tmp[8][2]=r[2];tmp[8][3]=r[3];goto L307;
}
L307:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[7][0]=r[0];tmp[7][2]=r[2];goto L308;
}
L308:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[7][1]=r[1];tmp[7][3]=r[3];goto L309;
}
L309:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[1],as[2],as[0],as[0]}};
const V &vs=src(24,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L310;
}
L310:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{-as[1],-as[2],-as[0],-as[0]}};
const V &vs=src(23,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
const V &cs=src(16,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L311;
}
L311:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{as[1],as[2],as[0],as[0]}};
const V &vs=src(16,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];goto L312;
}
L312:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{-as[1],-as[2],-as[0],-as[0]}};
const V &vs=src(24,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
const V &cs=src(23,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];goto L313;
}
L313:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[1],as[2],as[0],as[0]}};
const V &vs=src(24,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];goto L314;
}
L314:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{-as[1],-as[2],-as[0],-as[0]}};
const V &vs=src(23,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
const V &cs=src(22,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];pc=315;goto dispatch;
}
L315:if(++steps>0x40000)return;{
const V &as=src(60,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[8][0]=r[0];goto L316;
}
L316:if(++steps>0x40000)return;{
const V &as=src(61,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[8][1]=r[1];goto L317;
}
L317:if(++steps>0x40000)return;{
const V &as=src(62,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
tmp[8][2]=r[2];goto L318;
}
L318:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(24,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L319;
}
L319:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L320;
}
L320:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[8][0]=r[0];tmp[8][1]=r[1];tmp[8][2]=r[2];tmp[8][3]=r[3];goto L321;
}
L321:if(++steps>0x40000)return;{
const V &as=src(60,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[7][0]=r[0];goto L322;
}
L322:if(++steps>0x40000)return;{
const V &as=src(61,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[7][1]=r[1];goto L323;
}
L323:if(++steps>0x40000)return;{
const V &as=src(62,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[3],vs[3],vs[3],vs[3]}};
V r=a;
tmp[7][2]=r[2];goto L324;
}
L324:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(23,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L325;
}
L325:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L326;
}
L326:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];tmp[7][3]=r[3];goto L327;
}
L327:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[1],as[2],as[0],as[0]}};
const V &vs=src(24,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L328;
}
L328:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{-as[1],-as[2],-as[0],-as[0]}};
const V &vs=src(23,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
const V &cs=src(16,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L329;
}
L329:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{as[1],as[2],as[0],as[0]}};
const V &vs=src(16,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];goto L330;
}
L330:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{-as[1],-as[2],-as[0],-as[0]}};
const V &vs=src(24,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
const V &cs=src(23,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];goto L331;
}
L331:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[1],as[2],as[0],as[0]}};
const V &vs=src(24,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];goto L332;
}
L332:if(++steps>0x40000)return;{
const V &as=src(24,0); V a={{-as[1],-as[2],-as[0],-as[0]}};
const V &vs=src(23,0); V v={{vs[2],vs[0],vs[1],vs[1]}};
V r=a;
const V &cs=src(22,0); V c={{cs[0],cs[1],cs[2],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];pc=333;goto dispatch;
}
L333:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(22,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L334;
}
L334:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L335;
}
L335:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L336;
}
L336:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(23,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L337;
}
L337:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=1.0f/std::sqrt(a[0]);r={{d,d,d,d}};tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L338;
}
L338:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];tmp[7][3]=r[3];goto L339;
}
L339:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L340;
}
L340:if(++steps>0x40000)return;{
const V &as=src(57,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][0]=r[0];goto L341;
}
L341:if(++steps>0x40000)return;{
const V &as=src(58,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][1]=r[1];goto L342;
}
L342:if(++steps>0x40000)return;{
const V &as=src(59,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[6][2]=r[2];goto L343;
}
L343:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L344;
}
L344:if(++steps>0x40000)return;{
const V &as=src(57,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[7][0]=r[0];goto L345;
}
L345:if(++steps>0x40000)return;{
const V &as=src(58,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[7][1]=r[1];goto L346;
}
L346:if(++steps>0x40000)return;{
const V &as=src(59,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[7][2]=r[2];goto L347;
}
L347:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(29,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[6][0]=r[0];tmp[6][1]=r[1];tmp[6][2]=r[2];tmp[6][3]=r[3];goto L348;
}
L348:if(++steps>0x40000)return;{
const V &as=src(23,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(29,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[7][0]=r[0];tmp[7][1]=r[1];tmp[7][2]=r[2];tmp[7][3]=r[3];goto L349;
}
L349:if(++steps>0x40000)return;{
const V &as=src(115,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L350;
}
L350:if(++steps>0x40000)return;{
const V &as=src(114,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[2][0]=r[0];tmp[2][1]=r[1];tmp[2][2]=r[2];tmp[2][3]=r[3];goto L351;
}
L351:if(++steps>0x40000)return;{
const V &as=src(28,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(28,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][2]=r[2];goto L352;
}
L352:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(17,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L353;
}
L353:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(18,0); V c={{cs[0],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L354;
}
L354:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(18,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L355;
}
L355:if(++steps>0x40000)return;{
const V &as=src(113,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L356;
}
L356:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(17,0); V c={{cs[0],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L357;
}
L357:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(17,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L358;
}
L358:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(28,0); V v={{vs[2],vs[2],vs[2],vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][1]=r[1];goto L359;
}
L359:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
const V &cs=src(125,0); V c={{cs[1],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];goto L360;
}
L360:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{-as[1],-as[1],-as[1],-as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[0][2]=r[2];goto L361;
}
L361:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[2],as[1],as[0]}};
const V &vs=src(22,0); V v={{vs[0],vs[1],vs[0],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L362;
}
L362:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[2],as[2],as[2]}};
const V &vs=src(17,0); V v={{vs[1],vs[3],vs[3],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[6][0]=r[0];tmp[6][1]=r[1];goto L363;
}
L363:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[6][2]=r[2];tmp[6][3]=r[3];goto L364;
}
L364:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[2],as[1],as[0]}};
const V &vs=src(23,0); V v={{vs[0],vs[1],vs[0],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L365;
}
L365:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[2],as[2],as[2]}};
const V &vs=src(17,0); V v={{vs[1],vs[3],vs[3],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[7][0]=r[0];tmp[7][1]=r[1];goto L366;
}
L366:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[7][2]=r[2];tmp[7][3]=r[3];pc=367;goto dispatch;
}
L367:if(++steps>0x40000)return;{
pc=368;goto dispatch;
}
L368:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[15][3]=r[3];goto L369;
}
L369:if(++steps>0x40000)return;{
const V &as=src(38,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[15][0]=r[0];tmp[15][1]=r[1];tmp[15][2]=r[2];goto L370;
}
L370:if(++steps>0x40000)return;{
const V &as=src(66,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[10][0]=r[0];goto L371;
}
L371:if(++steps>0x40000)return;{
const V &as=src(67,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[10][1]=r[1];goto L372;
}
L372:if(++steps>0x40000)return;{
const V &as=src(68,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[10][2]=r[2];goto L373;
}
L373:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[10][3]=r[3];goto L374;
}
L374:if(++steps>0x40000)return;{
const V &as=src(122,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(26,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[15][0]=r[0];goto L375;
}
L375:if(++steps>0x40000)return;{
const V &as=src(123,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(26,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[15][1]=r[1];goto L376;
}
L376:if(++steps>0x40000)return;{
const V &as=src(124,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(26,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[15][2]=r[2];goto L377;
}
L377:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[15][3]=r[3];goto L378;
}
L378:if(++steps>0x40000)return;{
const V &as=src(69,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(22,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L379;
}
L379:if(++steps>0x40000)return;{
const V &as=src(69,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(23,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L380;
}
L380:if(++steps>0x40000)return;{
const V &as=src(31,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(16,0); V v={{-vs[0],-vs[1],-vs[2],-vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[15][0]=r[0];tmp[15][1]=r[1];tmp[15][2]=r[2];goto L381;
}
L381:if(++steps>0x40000)return;{
const V &as=src(31,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{-vs[0],-vs[1],-vs[2],-vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[15][0]=r[0];tmp[15][1]=r[1];tmp[15][2]=r[2];goto L382;
}
L382:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[1][0]=r[0];out[1][1]=r[1];out[1][2]=r[2];out[1][3]=r[3];goto L383;
}
L383:if(++steps>0x40000)return;{
const V &as=src(31,0); V a={{-as[0],-as[1],-as[2],-as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[2][0]=r[0];out[2][1]=r[1];out[2][2]=r[2];out[2][3]=r[3];goto L384;
}
L384:if(++steps>0x40000)return;{
const V &as=src(118,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[0][0]=r[0];goto L385;
}
L385:if(++steps>0x40000)return;{
const V &as=src(119,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[0][1]=r[1];goto L386;
}
L386:if(++steps>0x40000)return;{
const V &as=src(120,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[0][2]=r[2];goto L387;
}
L387:if(++steps>0x40000)return;{
const V &as=src(121,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(31,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};out[0][3]=r[3];goto L388;
}
L388:if(++steps>0x40000)return;{
const V &as=src(3,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
out[3][0]=r[0];out[3][1]=r[1];out[3][2]=r[2];goto L389;
}
L389:if(++steps>0x40000)return;{
const V &as=src(4,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[3][3]=r[3];goto L390;
}
L390:if(++steps>0x40000)return;{
const V &as=src(116,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(7,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L391;
}
L391:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=std::floor(a[k]);tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L392;
}
L392:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(17,0); V v={{-vs[0],-vs[1],-vs[2],-vs[3]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[3][0]=r[0];tmp[3][1]=r[1];tmp[3][2]=r[2];tmp[3][3]=r[3];goto L393;
}
L393:if(++steps>0x40000)return;{
const V &as=src(115,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L394;
}
L394:if(++steps>0x40000)return;{
const V &as=src(114,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[2][0]=r[0];tmp[2][1]=r[1];tmp[2][2]=r[2];tmp[2][3]=r[3];goto L395;
}
L395:if(++steps>0x40000)return;{
const V &as=src(19,0); V a={{as[0],as[0],as[0],as[0]}};
const V &vs=src(19,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][2]=r[2];goto L396;
}
L396:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(17,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(17,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L397;
}
L397:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(18,0); V c={{cs[0],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L398;
}
L398:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(18,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L399;
}
L399:if(++steps>0x40000)return;{
const V &as=src(113,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L400;
}
L400:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(17,0); V c={{cs[0],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L401;
}
L401:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
const V &cs=src(17,0); V c={{cs[2],cs[3],cs[3],cs[3]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L402;
}
L402:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[1],as[1],as[1],as[1]}};
const V &vs=src(19,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][1]=r[1];goto L403;
}
L403:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
const V &cs=src(125,0); V c={{cs[1],cs[1],cs[1],cs[1]}};
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k])+c[k];tmp[0][0]=r[0];goto L404;
}
L404:if(++steps>0x40000)return;{
const V &as=src(6,0); V a={{as[0],as[1],as[0],as[1]}};
const V &vs=src(16,0); V v={{vs[1],vs[0],vs[0],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[1][0]=r[0];tmp[1][1]=r[1];tmp[1][2]=r[2];tmp[1][3]=r[3];goto L405;
}
L405:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{-as[0],-as[0],-as[0],-as[0]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[1][0]=r[0];goto L406;
}
L406:if(++steps>0x40000)return;{
const V &as=src(126,0); V a={{-as[2],-as[2],-as[2],-as[2]}};
const V &vs=src(5,0); V v={{-vs[0],-vs[0],-vs[0],-vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[2][0]=r[0];goto L407;
}
L407:if(++steps>0x40000)return;{
const V &as=src(126,0); V a={{-as[2],-as[2],-as[2],-as[2]}};
const V &vs=src(5,0); V v={{vs[1],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[2][1]=r[1];goto L408;
}
L408:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[1],vs[1],vs[0],vs[0]}};
V r=a;
for(int k=0;k<4;k++)r[k]=mul(a[k],v[k]);tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];tmp[0][3]=r[3];goto L409;
}
L409:if(++steps>0x40000)return;{
const V &as=src(126,0); V a={{as[2],as[2],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[2][0]=r[0];tmp[2][1]=r[1];goto L410;
}
L410:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[2],as[3],as[3],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];goto L411;
}
L411:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
tmp[2][0]=r[0];tmp[2][1]=r[1];goto L412;
}
L412:if(++steps>0x40000)return;{
const V &as=src(125,0); V a={{as[0],as[0],as[0],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
tmp[2][2]=r[2];tmp[2][3]=r[3];goto L413;
}
L413:if(++steps>0x40000)return;{
const V &as=src(43,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[0][0]=r[0];goto L414;
}
L414:if(++steps>0x40000)return;{
const V &as=src(44,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[0][1]=r[1];goto L415;
}
L415:if(++steps>0x40000)return;{
const V &as=src(45,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2])+mul(a[3],v[3]);r={{d,d,d,d}};tmp[0][2]=r[2];goto L416;
}
L416:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[2],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
out[4][0]=r[0];out[4][1]=r[1];out[4][2]=r[2];out[4][3]=r[3];goto L417;
}
L417:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[0],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[1],vs[0],vs[0],vs[0]}};
V r=a;
tmp[2][0]=r[0];tmp[2][1]=r[1];goto L418;
}
L418:if(++steps>0x40000)return;{
const V &as=src(43,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];goto L419;
}
L419:if(++steps>0x40000)return;{
const V &as=src(44,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][1]=r[1];goto L420;
}
L420:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[1],as[1],as[1]}};
const V &vs=src(0,0); V v={{vs[1],vs[0],vs[0],vs[0]}};
V r=a;
out[5][0]=r[0];out[5][1]=r[1];goto L421;
}
L421:if(++steps>0x40000)return;{
const V &as=src(17,0); V a={{as[2],as[3],as[3],as[3]}};
const V &vs=src(0,0); V v={{vs[0],vs[1],vs[1],vs[1]}};
V r=a;
tmp[2][0]=r[0];tmp[2][1]=r[1];goto L422;
}
L422:if(++steps>0x40000)return;{
const V &as=src(43,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][0]=r[0];goto L423;
}
L423:if(++steps>0x40000)return;{
const V &as=src(44,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(18,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};tmp[0][1]=r[1];goto L424;
}
L424:if(++steps>0x40000)return;{
const V &as=src(16,0); V a={{as[0],as[0],as[0],as[1]}};
const V &vs=src(0,0); V v={{vs[0],vs[0],vs[0],vs[0]}};
V r=a;
out[5][2]=r[2];out[5][3]=r[3];goto L425;
}
L425:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(23,0); V v={{vs[0],vs[1],vs[2],vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L426;
}
L426:if(++steps>0x40000)return;{
const V &as=src(118,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};out[6][0]=r[0];goto L427;
}
L427:if(++steps>0x40000)return;{
const V &as=src(119,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};out[6][1]=r[1];goto L428;
}
L428:if(++steps>0x40000)return;{
const V &as=src(120,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};out[6][2]=r[2];goto L429;
}
L429:if(++steps>0x40000)return;{
const V &as=src(121,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};out[6][3]=r[3];goto L430;
}
L430:if(++steps>0x40000)return;{
const V &as=src(22,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(23,0); V v={{-vs[0],-vs[1],-vs[2],-vs[2]}};
V r=a;
for(int k=0;k<4;k++)r[k]=a[k]+v[k];tmp[0][0]=r[0];tmp[0][1]=r[1];tmp[0][2]=r[2];goto L431;
}
L431:if(++steps>0x40000)return;{
const V &as=src(118,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};out[7][0]=r[0];goto L432;
}
L432:if(++steps>0x40000)return;{
const V &as=src(119,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};out[7][1]=r[1];goto L433;
}
L433:if(++steps>0x40000)return;{
const V &as=src(120,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};out[7][2]=r[2];goto L434;
}
L434:if(++steps>0x40000)return;{
const V &as=src(121,0); V a={{as[0],as[1],as[2],as[2]}};
const V &vs=src(16,0); V v={{vs[0],vs[1],vs[2],vs[3]}};
V r=a;
float d=mul(a[0],v[0])+mul(a[1],v[1])+mul(a[2],v[2]);r={{d,d,d,d}};out[7][3]=r[3];goto L435;
}
L435:if(++steps>0x40000)return;{
return;}
}
