import { getPlatformOverview, type PlatformOverview } from './platform'

const overview: Promise<PlatformOverview> = getPlatformOverview()

void overview
