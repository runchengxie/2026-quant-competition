export function valueAxisLayout(width){
 if(!Number.isFinite(width)||width<0)throw new RangeError('Invalid chart width');
 return {splitNumber:width<600?3:5,axisLabel:{hideOverlap:true}};
}
