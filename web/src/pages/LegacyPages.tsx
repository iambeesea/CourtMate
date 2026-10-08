// Thin routes around the original MVP screens. Replaced by the database-backed
// Play and Player record screens later on this branch.
import { useState } from 'react'
import { useLegacySessions, useLegacyStats } from '../legacy/hooks'
import { MySessions, Stats, StoryModal } from '../legacy/LegacyScreens'
import { useToast } from '../state/toast'

export function LegacyPlay() {
  const notify = useToast()
  const { sessions, toggle } = useLegacySessions(notify)
  return <MySessions sessions={sessions} onJoin={toggle} />
}

export function LegacyRecord() {
  const stats = useLegacyStats()
  const [storyOpen, setStoryOpen] = useState(false)
  return (
    <>
      <Stats stats={stats} onShare={() => setStoryOpen(true)} />
      {storyOpen && <StoryModal stats={stats} onClose={() => setStoryOpen(false)} />}
    </>
  )
}
