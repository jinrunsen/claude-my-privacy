// Entirely fictional identities for isolated tests; never load user mappings.
export const TEST_MAPPINGS = [
  { from: '陈星河', to: '陈瑞恩' },
  { from: 'chenxinghe', to: 'ryanchen', casePairs: [{ from: 'ChenXingHe', to: 'RyanChen' }] },
  { from: '云杉智科', to: '海岚数科' },
  { from: 'cedarbyte', to: 'harborwave' },
];
export const TEST_CONFIG_PATH = '/synthetic/privacy/mappings.json';
export const TEST_CONFIG_TEXT = JSON.stringify({ mappings: TEST_MAPPINGS });
