import { useEffect, useState } from "react"
import { ChevronDown, ChevronUp, Lock, Search, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { getPlayers } from "@/lib/api"
import type { Player } from "@/lib/types"
import { playerKey } from "@/lib/types"

export function PlayerBrowser({
  lockedPlayers,
  excludedPlayers,
  onToggleLock,
  onToggleExclude,
  dataVersion,
}: {
  lockedPlayers: Set<string>
  excludedPlayers: Set<string>
  onToggleLock: (key: string) => void
  onToggleExclude: (key: string) => void
  dataVersion: number
}) {
  const [open, setOpen] = useState(false)
  const [players, setPlayers] = useState<Player[]>([])
  const [search, setSearch] = useState("")
  const [posFilter, setPosFilter] = useState("")
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    getPlayers()
      .then(setPlayers)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [open, dataVersion])

  const filtered = players.filter((p) => {
    if (search && !p.name.toLowerCase().includes(search.toLowerCase())) {
      return false
    }
    if (posFilter && p.position !== posFilter) return false
    return true
  })

  return (
    <div className="border-t">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium hover:bg-muted/50"
      >
        Player Browser ({players.length > 0 ? players.length : "..."})
        {open ? (
          <ChevronUp className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </button>
      {open && (
        <div className="px-4 pb-4">
          <div className="mb-3 flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search players..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex gap-1">
              {["", "F", "D", "G"].map((pos) => (
                <button
                  key={pos}
                  onClick={() => setPosFilter(pos)}
                  className={`px-2.5 py-1.5 text-xs ${
                    posFilter === pos
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {pos || "All"}
                </button>
              ))}
            </div>
          </div>
          {loading ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              Loading players...
            </p>
          ) : (
            <div className="max-h-96 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10"></TableHead>
                    <TableHead>Player</TableHead>
                    <TableHead>Team</TableHead>
                    <TableHead>Pos</TableHead>
                    <TableHead className="text-right">GP</TableHead>
                    <TableHead className="text-right">Proj</TableHead>
                    <TableHead className="text-right">Salary</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.slice(0, 100).map((player) => {
                    const pk = playerKey(player)
                    const isLocked = lockedPlayers.has(pk)
                    const isExcluded = excludedPlayers.has(pk)
                    return (
                      <TableRow key={pk}>
                        <TableCell className="flex gap-1 px-2">
                          <button
                            onClick={() => onToggleLock(pk)}
                            className={`p-0.5 ${isLocked ? "text-primary" : "text-muted-foreground/40 hover:text-muted-foreground"}`}
                          >
                            <Lock className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => onToggleExclude(pk)}
                            className={`p-0.5 ${isExcluded ? "text-destructive" : "text-muted-foreground/40 hover:text-muted-foreground"}`}
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </TableCell>
                        <TableCell className="font-medium">
                          {player.name}
                          {player.injured && (
                            <Badge
                              variant="destructive"
                              className="ml-2 text-[10px]"
                            >
                              INJ
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>{player.team}</TableCell>
                        <TableCell>{player.position}</TableCell>
                        <TableCell className="text-right">
                          {player.gamesThisWeek}
                        </TableCell>
                        <TableCell className="text-right">
                          {player.projFantasyPts}
                        </TableCell>
                        <TableCell className="text-right">
                          {player.salary > 0
                            ? `$${player.salary}M`
                            : "-"}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
              {filtered.length > 100 && (
                <p className="py-2 text-center text-xs text-muted-foreground">
                  Showing 100 of {filtered.length} players. Use search
                  to filter.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
