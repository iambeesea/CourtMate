import { useEffect, useState } from "react";
import { getPlayerStats } from "./api";
import { demoStats } from "./data";
import type { PlayerStats } from "./types";

export function useLegacyStats() {
  const [stats, setStats] = useState<PlayerStats>(demoStats);
  useEffect(() => {
    getPlayerStats().then(setStats);
  }, []);
  return stats;
}
