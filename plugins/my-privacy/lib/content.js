// Protocol identity, tool-use arguments, and signed thinking are not rewritable
// at session.append. Do not corrupt those fields while scrubbing visible text.
export function sanitizeBlocks(blocks, redact) {
  if (!Array.isArray(blocks)) throw new Error('Invalid content blocks');
  return blocks.flatMap(block => {
    if (block.type === 'text') return [{ ...block, text: redact(block.text) }];
    if (block.type === 'tool_result') {
      const content = typeof block.content === 'string'
        ? redact(block.content)
        : Array.isArray(block.content) ? sanitizeBlocks(block.content, redact) : block.content;
      return [{ ...block, content }];
    }
    // Unsupported media and signed/protocol blocks are opaque, not denied.
    return [block];
  });
}

export function redactAppend(event, redact) {
  return { ...event, message: { ...event.message, content: sanitizeBlocks(event.message.content, redact) } };
}

export function containsMedia(value, depth = 0) {
  if (depth > 80) throw new Error('Content too deeply nested');
  if (!value || typeof value !== 'object') return false;
  if (['image', 'document', 'audio', 'image_url'].includes(value.type)) return true;
  if (value.isImage === true || typeof value.base64 === 'string') return true;
  return Object.values(value).some(child => containsMedia(child, depth + 1));
}

export function rewriteToolResult(answer, redact) {
  if (!answer || typeof answer !== 'object' || Array.isArray(answer)) throw new Error('Invalid tool result envelope');
  if (answer.deny !== undefined) return { deny: redact(answer.deny) };
  // Core errors carry text/undefined, not the tool's typed output record.
  // Without ref, a replacement result is schema-validated (Bash requires an
  // object). Use the error channel instead; never replay core's raw messages.
  if (answer.isError === true) {
    const value = typeof answer.text === 'string' ? answer.text
      : typeof answer.result === 'string' ? answer.result : 'The tool failed without an error message.';
    return { deny: 'Underlying tool reported an error (execution may have occurred): ' + redact(value) };
  }
  // Never carry ref: it instructs the host to reuse the unmodified raw result.
  const result = { result: containsMedia(answer.result) ? redactAroundMedia(answer.result, redact) : redact(answer.result) };
  if (answer.isError !== undefined) result.isError = answer.isError;
  if (answer.context) result.context = redact(answer.context);
  return result;
}

function redactAroundMedia(value, redact, depth = 0) {
  if (depth > 80) throw new Error('Content too deeply nested');
  if (value === undefined) return value;
  if (!value || typeof value !== 'object') return redact(value);
  // Never apply literal name substitution inside opaque binary/base64 data.
  if (['image', 'document', 'audio', 'image_url'].includes(value.type) || value.isImage === true || typeof value.base64 === 'string') return value;
  if (Array.isArray(value)) return value.map(item => redactAroundMedia(item, redact, depth + 1));
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, redactAroundMedia(item, redact, depth + 1)]));
}

export function compactMessages(messages, redact) {
  return messages.map(message => {
    // A handle replays the original host-side message, ignoring rewritten text.
    const { handle, ...copy } = message;
    const filtered = { ...copy, text: redact(copy.text) };
    const scrubTool = tool => {
      const out = { ...tool };
      for (const key of ['input', 'result', 'text']) {
        if (tool[key] !== undefined) out[key] = redactAroundMedia(tool[key], redact);
      }
      // Preserve tool/tool_use_id and all other routing and protocol fields.
      return out;
    };
    if (copy.toolUses) filtered.toolUses = copy.toolUses.map(scrubTool);
    if (copy.toolResults) filtered.toolResults = copy.toolResults.map(scrubTool);
    // Keep opaque host content when no supported text needed replacement.
    return JSON.stringify(copy) === JSON.stringify(filtered) ? message : filtered;
  });
}
