#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

export function readJson(filePath) {
  return fs.existsSync(filePath) ? JSON.parse(fs.readFileSync(filePath, 'utf8')) : {};
}

export function toPosix(value) {
  return String(value).split(path.sep).join('/');
}

export function relativeToRoot(rootDir, filePath) {
  return toPosix(path.relative(rootDir, filePath));
}

export function tokenize(value) {
  return String(value)
    .toLowerCase()
    .match(/[a-z0-9][a-z0-9/_-]*/g) ?? [];
}

export function countTerms(tokens) {
  const counts = {};
  for (const token of tokens) {
    counts[token] = (counts[token] ?? 0) + 1;
  }
  return counts;
}

export function unique(tokens) {
  return [...new Set(tokens)];
}

export function loadRetrievalConfig(rootDir) {
  const config = readJson(path.join(rootDir, 'context-kit.json'));
  const retrieval = config.retrieval ?? {};
  return {
    config,
    retrieval: {
      enabled: retrieval.enabled ?? true,
      includePaths: retrieval.includePaths ?? [
        'README.md',
        'AGENTS.md',
        'ARCHITECTURE.md',
        'docs/SYSTEM_INTENT.md',
        'docs/CONTEXT_ENGINEERING.md',
        'docs/CONTEXT_EVALUATION.md',
        'docs/CONTEXT_PLATFORM.md',
        'docs/CONTEXTUAL_RETRIEVAL.md',
        'docs/AGENT_FACTORY.md',
        'docs/TOOL_DESIGN.md',
        'docs/AGENT_OBSERVABILITY.md',
        'docs/MULTI_AGENT_COORDINATION.md',
        'docs/SANDBOX_POLICY.md',
        'docs/DESIGN.md',
        'docs/ENGINEERING.md',
        'docs/PLANS.md',
        'docs/PRODUCT_SENSE.md',
        'docs/QUALITY_SCORE.md',
        'docs/RELIABILITY.md',
        'docs/SECURITY.md',
        'docs/HARNESS.md',
        'agents/',
        'tools/',
        'docs/design-docs/',
        'docs/product-specs/',
      ],
      excludePaths: retrieval.excludePaths ?? [
        'docs/archive/',
        'docs/generated/',
        '.agent-context/',
      ],
      chunkWords: Number(retrieval.chunkWords ?? 120),
      overlapWords: Number(retrieval.overlapWords ?? 30),
      defaultTopK: Number(retrieval.defaultTopK ?? 5),
      contextualWeight: Number(retrieval.contextualWeight ?? 0.65),
      rawWeight: Number(retrieval.rawWeight ?? 0.35),
      pathBoost: Number(retrieval.pathBoost ?? 0.8),
      headingBoost: Number(retrieval.headingBoost ?? 0.5),
      surfaceBoost: Number(retrieval.surfaceBoost ?? 0.75),
      indexPath: retrieval.indexPath ?? 'docs/generated/contextual-retrieval-index.json',
    },
  };
}

export function classifyAuthority(relPath) {
  if (relPath === 'README.md') return { role: 'root-router', authority: 'canonical' };
  if (relPath === 'AGENTS.md') return { role: 'agent-rules', authority: 'canonical' };
  if (relPath === 'ARCHITECTURE.md') return { role: 'architecture-map', authority: 'canonical' };
  if (relPath === 'docs/CONTEXT_ENGINEERING.md') return { role: 'context-engineering', authority: 'canonical' };
  if (relPath === 'docs/CONTEXT_EVALUATION.md') return { role: 'context-evaluation', authority: 'canonical' };
  if (relPath === 'docs/CONTEXT_PLATFORM.md') return { role: 'context-platform', authority: 'canonical' };
  if (relPath === 'docs/CONTEXTUAL_RETRIEVAL.md') return { role: 'contextual-retrieval', authority: 'canonical' };
  if (relPath === 'docs/AGENT_FACTORY.md') return { role: 'agent-factory', authority: 'canonical' };
  if (relPath === 'docs/TOOL_DESIGN.md') return { role: 'tool-design', authority: 'canonical' };
  if (relPath === 'docs/AGENT_OBSERVABILITY.md') return { role: 'agent-observability', authority: 'canonical' };
  if (relPath === 'docs/MULTI_AGENT_COORDINATION.md') return { role: 'coordination', authority: 'canonical' };
  if (relPath === 'docs/SANDBOX_POLICY.md') return { role: 'sandbox-policy', authority: 'canonical' };
  if (relPath.startsWith('agents/')) return { role: 'agent-blueprint', authority: 'canonical' };
  if (relPath.startsWith('tools/')) return { role: 'tool-contract', authority: 'canonical' };
  if (relPath.startsWith('docs/design-docs/')) return { role: 'design-doc', authority: 'canonical' };
  if (relPath.startsWith('docs/product-specs/')) return { role: 'surface-spec', authority: 'canonical' };
  if (relPath.startsWith('docs/exec-plans/active/')) return { role: 'active-plan', authority: 'canonical' };
  return { role: 'doc', authority: 'tracked' };
}

function walkMarkdown(dirPath) {
  if (!dirPath || !fs.existsSync(dirPath)) return [];
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...walkMarkdown(fullPath));
      continue;
    }
    if (entry.name.endsWith('.md')) files.push(fullPath);
  }
  return files;
}

function includeEntry(rootDir, entry) {
  const resolved = path.join(rootDir, entry);
  if (!fs.existsSync(resolved)) return [];
  const stats = fs.statSync(resolved);
  if (stats.isDirectory()) return walkMarkdown(resolved);
  return [resolved];
}

export function sourceFiles(rootDir, retrieval) {
  const excludePrefixes = (retrieval.excludePaths ?? []).map((item) => item.replace(/\/+$/, ''));
  const files = [...new Set((retrieval.includePaths ?? []).flatMap((entry) => includeEntry(rootDir, entry)))];
  return files
    .map((filePath) => ({ filePath, relPath: relativeToRoot(rootDir, filePath) }))
    .filter(({ relPath }) => !excludePrefixes.some((prefix) => relPath === prefix || relPath.startsWith(`${prefix}/`)))
    .sort((left, right) => left.relPath.localeCompare(right.relPath));
}

function flushSection(sections, lines, headings) {
  const text = lines.join('\n').trim();
  if (!text) return;
  sections.push({
    headings: headings.map((item) => item.text),
    text,
  });
}

function parseSections(markdown) {
  const lines = markdown.split('\n');
  const sections = [];
  const headingStack = [];
  let buffer = [];

  for (const line of lines) {
    const headingMatch = line.match(/^(#{1,6})\s+(.+?)\s*$/);
    if (headingMatch) {
      flushSection(sections, buffer, headingStack);
      buffer = [];
      const depth = headingMatch[1].length;
      const text = headingMatch[2].replace(/`/g, '').trim();
      while (headingStack.length >= depth) headingStack.pop();
      headingStack.push({ depth, text });
      continue;
    }
    buffer.push(line);
  }

  flushSection(sections, buffer, headingStack);
  return sections.length ? sections : [{ headings: [], text: markdown.trim() }];
}

function chunkWords(text, chunkSize, overlapSize) {
  const tokens = text.split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return [];
  const chunks = [];
  const step = Math.max(1, chunkSize - overlapSize);
  for (let start = 0; start < tokens.length; start += step) {
    const slice = tokens.slice(start, start + chunkSize);
    if (slice.length === 0) break;
    chunks.push(slice.join(' '));
    if (start + chunkSize >= tokens.length) break;
  }
  return chunks;
}

function surfaceOwners(config, relPath) {
  const owners = [];
  for (const surface of config.surfaces ?? []) {
    if (surface.spec === relPath) owners.push(surface.id);
  }
  return owners;
}

function contextualPrefix({ relPath, role, authority, headings, surfaces }) {
  const headingText = headings.length ? headings.join(' > ') : 'root';
  const surfaceText = surfaces.length ? surfaces.join(', ') : 'none';
  return [
    `Document path: ${relPath}.`,
    `Role: ${role}.`,
    `Authority: ${authority}.`,
    `Section: ${headingText}.`,
    `Surface owners: ${surfaceText}.`,
  ].join(' ');
}

function bm25Score(queryTokens, counts, docLength, averageLength, documentFrequency, totalDocs) {
  if (!queryTokens.length || !docLength || !averageLength || !totalDocs) return 0;
  const k1 = 1.2;
  const b = 0.75;
  let score = 0;
  for (const term of queryTokens) {
    const tf = counts[term] ?? 0;
    if (!tf) continue;
    const df = documentFrequency[term] ?? 0;
    const idf = Math.log(1 + ((totalDocs - df + 0.5) / (df + 0.5)));
    score += idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + (b * docLength) / averageLength)));
  }
  return score;
}

export function buildRetrievalIndex(rootDir) {
  const { config, retrieval } = loadRetrievalConfig(rootDir);
  const sources = sourceFiles(rootDir, retrieval);
  const chunks = [];

  for (const source of sources) {
    const markdown = fs.readFileSync(source.filePath, 'utf8');
    const { role, authority } = classifyAuthority(source.relPath);
    const surfaces = surfaceOwners(config, source.relPath);
    const sections = parseSections(markdown);

    sections.forEach((section, sectionIndex) => {
      const sectionChunks = chunkWords(section.text, retrieval.chunkWords, retrieval.overlapWords);
      sectionChunks.forEach((text, chunkIndex) => {
        const prefix = contextualPrefix({
          relPath: source.relPath,
          role,
          authority,
          headings: section.headings,
          surfaces,
        });
        const rawTokens = tokenize(text);
        const contextualText = `${prefix}\n\n${text}`;
        const contextualTokens = tokenize(contextualText);
        const preview = text.slice(0, 240).replace(/\s+/g, ' ').trim();
        chunks.push({
          id: `${source.relPath}#${sectionIndex + 1}.${chunkIndex + 1}`,
          path: source.relPath,
          role,
          authority,
          headings: section.headings,
          surfaces,
          preview,
          rawText: text,
          contextualText,
          rawCounts: countTerms(rawTokens),
          contextualCounts: countTerms(contextualTokens),
          rawLength: rawTokens.length,
          contextualLength: contextualTokens.length,
        });
      });
    });
  }

  const contextDf = {};
  const rawDf = {};
  for (const chunk of chunks) {
    for (const token of unique(Object.keys(chunk.contextualCounts))) {
      contextDf[token] = (contextDf[token] ?? 0) + 1;
    }
    for (const token of unique(Object.keys(chunk.rawCounts))) {
      rawDf[token] = (rawDf[token] ?? 0) + 1;
    }
  }

  const avgContextLength = chunks.length
    ? chunks.reduce((sum, chunk) => sum + chunk.contextualLength, 0) / chunks.length
    : 0;
  const avgRawLength = chunks.length
    ? chunks.reduce((sum, chunk) => sum + chunk.rawLength, 0) / chunks.length
    : 0;

  return {
    version: 1,
    retrieval,
    sourceCount: sources.length,
    chunkCount: chunks.length,
    avgContextLength,
    avgRawLength,
    contextDf,
    rawDf,
    chunks,
  };
}

export function scoreRetrieval(index, query, options = {}) {
  const topK = Number.isFinite(options.topK) && options.topK > 0 ? options.topK : (index.retrieval?.defaultTopK ?? 5);
  const queryTokens = unique(tokenize(query));
  const surface = options.surface ? String(options.surface) : '';
  const pathFilter = options.path ? String(options.path) : '';
  const totalDocs = index.chunkCount ?? index.chunks?.length ?? 0;

  const results = (index.chunks ?? [])
    .filter((chunk) => !surface || chunk.surfaces.includes(surface))
    .filter((chunk) => !pathFilter || chunk.path.startsWith(pathFilter))
    .map((chunk) => {
      const contextualScore = bm25Score(queryTokens, chunk.contextualCounts, chunk.contextualLength, index.avgContextLength, index.contextDf, totalDocs);
      const rawScore = bm25Score(queryTokens, chunk.rawCounts, chunk.rawLength, index.avgRawLength, index.rawDf, totalDocs);
      const hayPath = `${chunk.path} ${(chunk.headings ?? []).join(' ')}`.toLowerCase();
      const pathMatches = queryTokens.filter((term) => chunk.path.toLowerCase().includes(term)).length;
      const headingMatches = queryTokens.filter((term) => hayPath.includes(term)).length;
      const surfaceMatch = surface && chunk.surfaces.includes(surface) ? 1 : 0;
      const score = (
        contextualScore * (index.retrieval?.contextualWeight ?? 0.65) +
        rawScore * (index.retrieval?.rawWeight ?? 0.35) +
        pathMatches * (index.retrieval?.pathBoost ?? 0.8) +
        headingMatches * (index.retrieval?.headingBoost ?? 0.5) +
        surfaceMatch * (index.retrieval?.surfaceBoost ?? 0.75)
      );
      return { ...chunk, score };
    })
    .filter((chunk) => chunk.score > 0)
    .sort((left, right) => right.score - left.score || left.path.localeCompare(right.path) || left.id.localeCompare(right.id));

  return results.slice(0, topK);
}
