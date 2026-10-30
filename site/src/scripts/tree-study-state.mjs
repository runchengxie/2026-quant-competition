/** Strict intersection of explicit selectors; null results stay in the selected rows. */
export function matches(row, selection) {
  return Object.entries(selection).every(([key,value])=>String(row[key])===String(value));
}
