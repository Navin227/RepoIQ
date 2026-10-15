import React from 'react';

interface Props {
  analysisRunId?: string;
  children: React.ReactNode;
}

interface State {
  failed: boolean;
}

export default class AnalysisDiagnosticsBoundary extends React.Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[RepoIQ analysis]', {
      analysis_run_id: this.props.analysisRunId || 'missing',
      event: 'frontend_result_render_failed',
      error_type: error.name,
      component_stack: info.componentStack?.slice(0, 2000),
    });
  }

  render() {
    if (this.state.failed) {
      return <div role="alert">Analysis result could not be rendered. Correlation ID: {this.props.analysisRunId || 'unavailable'}</div>;
    }
    return this.props.children;
  }
}
