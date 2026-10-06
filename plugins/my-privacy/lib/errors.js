// Only fixed reason codes cross the privacy boundary; exception messages may
// include raw file paths, tool output, or credentials and must never be echoed.
const SAFE_CODES = new Set([
  'INVALID_JSON', 'CYCLIC_JSON', 'KEY_COLLISION', 'SIZE_LIMIT', 'DEPTH_LIMIT',
  'NODE_LIMIT', 'MAPPING_LIMIT', 'AMBIGUOUS_ALIAS_CASE', 'UNKNOWN_PII_TOKEN',
  'AMBIGUOUS_PATH', 'AMBIGUOUS_NEW_PATH', 'PATH_NOT_FOUND', 'SHELL_PII_TOKEN',
  'COMPLEX_ALIAS_COMMAND', 'UNSUPPORTED_ALIAS_COMMAND', 'EXTERNAL_COMMAND_OPTION',
  'RELATIVE_ALIAS_AFTER_CD', 'PATH_LOOKUP_LIMIT', 'SHORT_IDENTIFIER_COLLISION',
  'EDIT_MATCH_AMBIGUOUS', 'EDIT_MATCH_NOT_FOUND',
]);
const SAFE_STAGES = new Set(['arguments', 'prepare', 'path-check', 'preflight', 'execute', 'result', 'hook']);

export function policyError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}

export function isPolicyError(error) {
  return SAFE_CODES.has(error?.code);
}

export function toolFailure(stage, error) {
  const code = isPolicyError(error) ? error.code : 'INTERNAL_ERROR';
  const phase = SAFE_STAGES.has(stage) ? stage : 'hook';
  if (code === 'PATH_NOT_FOUND') return { deny: 'Local file path was not found [PATH_NOT_FOUND]. Use Glob or Grep on an existing directory to locate the actual file.' };
  if (code === 'UNKNOWN_PII_TOKEN') return { deny: 'MyPrivacy guard withheld this tool call [UNKNOWN_PII_TOKEN]. This PII token belongs to an unavailable session mapping. Read the source again in a new session.' };
  if (code === 'COMPLEX_ALIAS_COMMAND' || code === 'UNSUPPORTED_ALIAS_COMMAND') {
    return { deny: `MyPrivacy guard withheld this tool call [prepare:${code}]. Use a leading cd with one literal absolute directory path followed by && or ;, and relative paths inside the script; or use local file tools. Native tool permissions still apply.` };
  }
  const advice = phase === 'result'
    ? 'The tool already ran, but its output could not be safely filtered.'
    : phase === 'execute' ? 'The underlying tool did not return a usable result.'
      : 'Use verified file paths and local file tools, or a leading literal cd directory followed by && or ;.';
  return { deny: `MyPrivacy guard withheld this tool call or result [${phase}:${code}]. ${advice}` };
}
