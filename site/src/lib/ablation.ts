import {existsSync,readFileSync} from "node:fs";
import {resolve} from "node:path";
/** The privacy gate validates this exact reviewed artifact before deployment. */
export function loadAblation(){
 const path=resolve(process.cwd(),"src/data/ablation-study.v1.json");
 if(!existsSync(path))return null;
 const value=JSON.parse(readFileSync(path,"utf8"));
 if(value.schema!=="competition.public_ablation.v1"||!Array.isArray(value.results)||!Array.isArray(value.methods)||value.origin?.retrospective!==true||value.origin?.accepted_research!==false)throw Error("Invalid reviewed ablation artifact");
 return value;
}
