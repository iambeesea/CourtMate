// Thin route around the original MVP player record. Replaced by the
// database-backed record in phase 4.
import { useState } from 'react'
import { useLegacyStats } from '../legacy/hooks'
import { Stats, StoryModal } from '../legacy/LegacyScreens'

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
