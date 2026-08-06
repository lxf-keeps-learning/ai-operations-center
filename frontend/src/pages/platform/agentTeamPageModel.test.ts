import assert from 'node:assert/strict'

import { buildTeamDetails, getTeamMemberLinks, getRouteLinks } from './agentTeamPageModel'

const team = buildTeamDetails()
const supervisor = team.members.find((member) => member.key === 'supervisor')
const safetyRoute = team.routes.find((route) => route.key === 'safety')

assert.ok(supervisor)
assert.ok(safetyRoute)
assert.equal(team.code, 'operation_analysis_team')
assert.equal(team.nodes[0]?.key, 'supervisor_route')
assert.equal(getTeamMemberLinks(supervisor!).agent, '/platform/agents?agent=supervisor')
assert.equal(getRouteLinks(safetyRoute!).agent, '/platform/agents?agent=safety')

console.log('agent team page model checks passed')
