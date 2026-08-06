import assert from 'node:assert/strict'

import { buildAgentDetails, getAgentActionLinks } from './agentPageModel'

const details = buildAgentDetails()
const operation = details.find((agent) => agent.key === 'operation')

assert.ok(operation)
assert.equal(operation?.model, '默认运行时')
assert.equal(operation?.graphType, 'report_generation')
assert.equal(operation?.promptLabel, '运营分析默认策略')

const links = getAgentActionLinks(operation!)
assert.equal(links.graph, '/platform/graphs?type=report_generation')
assert.equal(links.prompt, '/prompt-center?agent=operation')
assert.equal(links.model, '/infra/models?agent=operation')

console.log('agent page model checks passed')
