import * as React from 'react';
import {Redirect, Route, RouteComponentProps, Switch} from 'react-router-dom';

import {PipelineExecutionRoot} from '../execute/PipelineExecutionRoot';
import {PipelineExecutionSetupRoot} from '../execute/PipelineExecutionSetupRoot';
import {PipelineNav} from '../nav/PipelineNav';
import {PipelinePartitionsRoot} from '../partitions/PipelinePartitionsRoot';
import {RepoAddress} from '../workspace/types';

import {PipelineExplorerRegexRoot} from './PipelineExplorerRoot';
import {PipelineOverviewRoot} from './PipelineOverviewRoot';
import {PipelineRunsRoot} from './PipelineRunsRoot';

interface Props {
  repoAddress: RepoAddress;
}

export const PipelineRoot: React.FC<Props> = (props) => {
  const {repoAddress} = props;
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        width: '100%',
        height: '100%',
      }}
    >
      <PipelineNav repoAddress={repoAddress} />
      <Switch>
        <Route
          path="/workspace/:repoPath/pipelines/:pipelinePath/overview"
          render={(props) => <PipelineOverviewRoot {...props} repoAddress={repoAddress} />}
        />
        <Route
          path="/workspace/:repoPath/pipelines/:pipelinePath/playground/setup"
          component={(props: RouteComponentProps<{pipelinePath: string}>) => (
            <PipelineExecutionSetupRoot
              pipelinePath={props.match.params.pipelinePath}
              repoAddress={repoAddress}
            />
          )}
        />
        <Route
          path="/workspace/:repoPath/pipelines/:pipelinePath/playground"
          component={(props: RouteComponentProps<{pipelinePath: string}>) => (
            <PipelineExecutionRoot
              pipelinePath={props.match.params.pipelinePath}
              repoAddress={repoAddress}
            />
          )}
        />
        <Route
          path="/workspace/:repoPath/pipelines/:pipelinePath/runs/:runId"
          render={(props: RouteComponentProps<{runId: string}>) => (
            <Redirect to={`/instance/runs/${props.match.params.runId}`} />
          )}
        />
        {/* Move to `/instance`: */}
        <Route
          path="/workspace/:repoPath/pipelines/:pipelinePath/runs"
          component={(props: RouteComponentProps<{pipelinePath: string}>) => (
            <PipelineRunsRoot pipelinePath={props.match.params.pipelinePath} />
          )}
        />
        <Route
          path="/workspace/:repoPath/pipelines/:pipelinePath/partitions"
          render={(props: RouteComponentProps<{pipelinePath: string}>) => (
            <PipelinePartitionsRoot
              pipelinePath={props.match.params.pipelinePath}
              repoAddress={repoAddress}
            />
          )}
        />
        {/* Capture solid subpath in a regex match */}
        <Route
          path="/workspace/:repoPath/pipelines/(/?.*)"
          render={(props: RouteComponentProps) => (
            <PipelineExplorerRegexRoot {...props} repoAddress={repoAddress} />
          )}
        />
      </Switch>
    </div>
  );
};
