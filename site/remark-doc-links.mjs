import { dirname, resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { documentRoutes } from "./document-routes.mjs";

const root=fileURLToPath(new URL("../",import.meta.url));
export function rewriteDocumentationLink(url, filename, image=false) {
  if(!url || /^(?:[a-z][a-z0-9+.-]*:|\/\/|#|\/)/i.test(url)) return url;
  const hash=url.indexOf("#");
  const fragment=hash<0?"":url.slice(hash);
  const path=hash<0?url:url.slice(0,hash);
  const target=relative(root,resolve(dirname(filename),path)).replaceAll("\\","/");
  if(target.startsWith("../")) return url;
  const doc=documentRoutes.find(entry=>entry.source===target);
  if(doc && !image) return doc.route+fragment;
  const encoded=target.split("/").map(encodeURIComponent).join("/");
  return (image?"https://raw.githubusercontent.com/runchengxie/global-market-research/main/":"https://github.com/runchengxie/global-market-research/blob/main/")+encoded+fragment;
}

export default function documentationLinks() {
  return (tree,file)=>{
    if(!file.path || !documentRoutes.some(entry=>resolve(root,entry.source)===resolve(file.path))) return;
    const walk=node=>{
      if(node.type==="link" || node.type==="image") node.url=rewriteDocumentationLink(node.url,file.path,node.type==="image");
      for(const child of node.children??[]) walk(child);
    };
    walk(tree);
  };
}
