import type { DrilldownNode, SearchResult } from '../types/api';

/**
 * Compose a search query that inherits the parent context for a drilldown
 * or find-out-more sub-query.
 *
 * Without this, "find out more" on a fact like *"improved food security"*
 * inside a parent query *"cash transfers in Niger"* would search just the
 * fact text — returning chunks about food security from anywhere — and only
 * the summarisation prompt would mention the parent. Passing the parent
 * context through to the search itself narrows retrieval to chunks that are
 * relevant to *both* the leaf and the surrounding investigation.
 *
 * The included context mirrors what the summarisation prompt does:
 *   - the root query is always included (broad framing),
 *   - the immediate parent label is added when the user has drilled down
 *     past the root (specificity),
 *   - the deeper ancestor chain is intentionally omitted to avoid keyword
 *     dilution at deep levels.
 *
 * The returned string is plain text suitable for both dense embedding and
 * sparse keyword retrieval — no quotes or operators that the search backend
 * would treat as syntax.
 */
export const buildContextualSearchQuery = (
  leafQuery: string,
  rootQuery: string,
  parentLabel?: string | null,
): string => {
  const leaf = leafQuery.trim();
  const root = rootQuery.trim();
  // Empty root or root === leaf: just return the leaf — no useful context to add.
  if (!root || root === leaf) return leaf;
  const parts: string[] = [leaf, root];
  // Only add the immediate parent if it's distinct from both leaf and root,
  // matching how the summary prompt avoids redundant phrases.
  const parent = (parentLabel || '').trim();
  if (parent && parent !== leaf && parent !== root) {
    parts.splice(1, 0, parent);
  }
  return parts.join(' ');
};

/**
 * Serialize a drilldown tree for activity/rating logging.
 * Strips heavy data (results arrays, summaries, prompts) to keep the payload small.
 * Preserves only the tree structure (ids + labels) so admins can see which
 * topics the user explored.
 */
export const serializeDrilldownTree = (
  node: DrilldownNode,
): Record<string, any> => ({
  id: node.id,
  label: node.label,
  children: node.children.map(serializeDrilldownTree),
});

/**
 * Strip heavy fields from a search result for storage.
 * Keeps display-relevant fields (title, text snippet, headings, score, etc.)
 * but drops metadata (~90KB each), chunk_elements, tables, images, etc.
 */
const slimResult = (r: SearchResult): Record<string, any> => ({
  chunk_id: r.chunk_id,
  doc_id: r.doc_id,
  text: r.text,
  title: r.title,
  document_title: (r as any).document_title,
  headings: r.headings,
  score: r.score,
  page_num: r.page_num,
  section_type: (r as any).section_type,
  organization: r.organization,
  year: r.year,
  data_source: (r as any).data_source,
  item_types: r.item_types,
  bbox: r.bbox,
});

/**
 * Serialize the full drilldown tree for saving research.
 * Preserves summaries, translations, and slim results (no heavy metadata).
 * Strips prompts (regenerated on drilldown) and large result fields
 * (metadata, chunk_elements, tables, images) to keep payload under 10 MB.
 */
export const serializeFullDrilldownTree = (
  node: DrilldownNode,
): Record<string, any> => ({
  id: node.id,
  label: node.label,
  summary: node.summary,
  prompt: '',
  results: node.results.map(slimResult),
  translatedText: node.translatedText,
  translatedLang: node.translatedLang,
  expanded: node.expanded,
  children: node.children.map(serializeFullDrilldownTree),
});

/**
 * Return a deep copy of the tree with one node's summary/results patched in.
 * Used before export/save to ensure the currently-viewed node has its live state.
 */
export const patchNodeInTree = (
  node: DrilldownNode,
  targetId: string,
  summary: string,
  nodeResults: SearchResult[]
): DrilldownNode => {
  if (node.id === targetId) {
    return { ...node, summary, results: nodeResults, children: node.children.map((c) => ({ ...c })) };
  }
  return {
    ...node,
    children: node.children.map((c) => patchNodeInTree(c, targetId, summary, nodeResults)),
  };
};
