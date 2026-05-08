import { useState, useEffect } from "react";

export interface WorkflowSettings {
  documentRetrievalPremiumThreshold: number;
  policyComparisonPremiumThreshold: number;
  enableSmartRecommendations: boolean;
}

const DEFAULT_SETTINGS: WorkflowSettings = {
  documentRetrievalPremiumThreshold: 8000,
  policyComparisonPremiumThreshold: 10000,
  enableSmartRecommendations: true,
};

const STORAGE_KEY = "workflow-settings";

export function useWorkflowSettings() {
  const [settings, setSettings] = useState<WorkflowSettings>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) };
      }
    } catch (e) {
      console.error("Failed to load workflow settings:", e);
    }
    return DEFAULT_SETTINGS;
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch (e) {
      console.error("Failed to save workflow settings:", e);
    }
  }, [settings]);

  const updateSettings = (updates: Partial<WorkflowSettings>) => {
    setSettings(prev => ({ ...prev, ...updates }));
  };

  const resetToDefaults = () => {
    setSettings(DEFAULT_SETTINGS);
  };

  return {
    settings,
    updateSettings,
    resetToDefaults,
    DEFAULT_SETTINGS,
  };
}

// Export a function to get settings without hook (for use in non-component contexts)
export function getWorkflowSettings(): WorkflowSettings {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(stored) };
    }
  } catch (e) {
    console.error("Failed to load workflow settings:", e);
  }
  return DEFAULT_SETTINGS;
}
