const methods=['equal_hold','momentum','cnn_rank_daily','cnn_rank_weekly','matched_numeric','matched_image'];
export function selectSummary(data,exposure,fee) {
  if (![40,100].includes(exposure) || ![0,20,40].includes(fee)) throw new Error('Unsupported scenario');
  const rows=methods.map(strategy=>data.records.filter(r=>r.exposure===exposure && r.fee_bps===fee && r.strategy===strategy));
  if (rows.some(group=>group.length!==1 || group[0].windows!==9)) throw new Error('Incomplete summary');
  return rows.map(group=>group[0]);
}
