import {gql, useApolloClient, useMutation} from '@apollo/client';
import {Button, Icon, Intent, Tooltip} from '@blueprintjs/core';
import * as React from 'react';

import {SharedToaster} from '../app/DomUtils';
import {useInvalidateConfigsForRepo} from '../app/LocalStorage';
import {ShortcutHandler} from '../app/ShortcutHandler';
import {Spinner} from '../ui/Spinner';

import {
  ReloadRepositoryLocationMutation,
  ReloadRepositoryLocationMutationVariables,
} from './types/ReloadRepositoryLocationMutation';

type ReloadResult = {type: 'success'} | {type: 'error'; message: string} | {type: 'loading'};
type OnReload = (location: string, result: ReloadResult) => void;

export const useRepositoryLocationReload = (location: string, onReload: OnReload = () => {}) => {
  const apollo = useApolloClient();
  const [reload] = useMutation<
    ReloadRepositoryLocationMutation,
    ReloadRepositoryLocationMutationVariables
  >(RELOAD_REPOSITORY_LOCATION_MUTATION, {
    variables: {location},
  });
  const [reloading, setReloading] = React.useState(false);
  const invalidateConfigs = useInvalidateConfigsForRepo();

  const onClick = async (e: React.MouseEvent | KeyboardEvent) => {
    e.stopPropagation();

    setReloading(true);
    const {data} = await reload();
    setReloading(false);

    let loadFailure = null;
    let loadStatus = null;
    switch (data?.reloadRepositoryLocation.__typename) {
      case 'RepositoryLocation':
        loadStatus = data?.reloadRepositoryLocation.loadStatus;
        break;
      case 'RepositoryLocationLoadFailure':
        loadStatus = data?.reloadRepositoryLocation.loadStatus;
        loadFailure = data?.reloadRepositoryLocation.error.message;
        break;
      default:
        loadFailure = data?.reloadRepositoryLocation.message;
        break;
    }

    if (loadFailure) {
      SharedToaster.show({
        message: 'Repository Location Reloaded with Errors',
        timeout: 3000,
        icon: 'refresh',
        intent: Intent.DANGER,
      });
      onReload(location, {type: 'error', message: loadFailure});
    } else if (loadStatus === 'LOADED') {
      SharedToaster.show({
        message: 'Repository Location Reloaded',
        timeout: 3000,
        icon: 'refresh',
        intent: Intent.SUCCESS,
      });
      onReload(location, {type: 'success'});
    } else {
      onReload(location, {type: 'loading'});
    }

    // Update run config localStorage, which may now be out of date.
    const repositories =
      data?.reloadRepositoryLocation.__typename === 'RepositoryLocation'
        ? data.reloadRepositoryLocation.repositories
        : [];

    invalidateConfigs(repositories);

    // clears and re-fetches all the queries bound to the UI
    apollo.resetStore();
  };

  return {reloading, onClick};
};

interface Props {
  locations: string[];
}

export const ReloadRepositoryLocationButton: React.FC<Props> = (props) => {
  const {locations} = props;

  // todo dish: Allow reloading multiple!
  const {reloading, onClick} = useRepositoryLocationReload(locations[0]);

  if (!locations.length) {
    return null;
  }

  return (
    <ShortcutHandler
      onShortcut={onClick}
      shortcutLabel={`⌥R`}
      shortcutFilter={(e) => e.keyCode === 82 && e.altKey}
    >
      <Tooltip
        className="bp3-dark"
        hoverOpenDelay={500}
        hoverCloseDelay={0}
        content={'Reload metadata from this repository location.'}
      >
        <Button
          icon={reloading ? <Spinner purpose="body-text" /> : <Icon icon="refresh" iconSize={12} />}
          disabled={reloading}
          onClick={onClick}
        />
      </Tooltip>
    </ShortcutHandler>
  );
};

const RELOAD_REPOSITORY_LOCATION_MUTATION = gql`
  mutation ReloadRepositoryLocationMutation($location: String!) {
    reloadRepositoryLocation(repositoryLocationName: $location) {
      __typename
      ... on RepositoryLocation {
        id
        repositories {
          id
          name
          pipelines {
            id
            name
          }
        }
        loadStatus
      }
      ... on ReadOnlyError {
        message
      }
      ... on ReloadNotSupported {
        message
      }
      ... on RepositoryLocationNotFound {
        message
      }
      ... on RepositoryLocationLoadFailure {
        id
        error {
          message
        }
        loadStatus
      }
    }
  }
`;
