import {useMemo} from 'react';

import type {Project} from 'sentry/types/project';
import {defined} from 'sentry/utils';
import type EventView from 'sentry/utils/discover/eventView';

export function useEventViewProject(eventView: EventView, projects: Project[]) {
  return useMemo(() => {
    if (!defined(eventView)) {
      return undefined;
    }

    const projectId = String(eventView.project[0]);

    return projects.find(proj => proj.id === projectId);
  }, [eventView, projects]);
}
