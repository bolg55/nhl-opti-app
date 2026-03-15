export interface Player {
  name: string
  team: string
  position: string
  gamesThisWeek: number
  projFantasyPts: number
  salary: number
  injured: boolean
  injuryDescription: string | null
}

export function playerKey(p: { name: string; team: string; position: string }): string {
  return `${p.name}|${p.team}|${p.position}`
}

export interface LineupResult {
  players: Player[]
  totalPoints: number
  totalSalary: number
  feasible: boolean
  message?: string
}

export interface Settings {
  max_cost: number
  min_cost_pct: number
  num_forwards: number
  num_defensemen: number
  num_goalies: number
  max_per_team: number
  min_games_played: number
}

export interface AuthResponse {
  authenticated: boolean
}
