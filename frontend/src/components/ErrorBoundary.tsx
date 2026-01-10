import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Result, Button } from 'antd-mobile';
import { FrownOutline } from 'antd-mobile-icons';

interface Props {
    children?: ReactNode;
}

interface State {
    hasError: boolean;
    error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false
    };

    public static getDerivedStateFromError(error: Error): State {
        // Update state so the next render will show the fallback UI.
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        // Log errors to monitoring service
        console.error('Uncaught error:', error, errorInfo);

        /**
         * TODO: Log to a real monitoring service like Sentry or LogRocket
         * Example: 
         * Sentry.captureException(error, { extra: errorInfo });
         */
    }

    private handleReset = () => {
        // Instead of just resetting state, we should redirect to home 
        // to ensure a clean state if the error was due to specific route data
        window.location.href = '/';
    };

    public render() {
        if (this.state.hasError) {
            return (
                <div className="page-container safe-area-padding error-boundary-container">
                    <Result
                        status="error"
                        icon={<FrownOutline className="error-boundary-icon" />}
                        title="Something went wrong"
                        description="We encountered an unexpected error. Please try refreshing the page."
                    />
                    <div className="error-boundary-content">
                        <Button
                            block
                            color="primary"
                            onClick={this.handleReset}
                        >
                            Return to Dashboard
                        </Button>

                        {import.meta.env.DEV && this.state.error && (
                            <div className="error-boundary-details">
                                <strong>Error Details:</strong>
                                <pre>
                                    {this.state.error.stack || this.state.error.message}
                                </pre>
                            </div>
                        )}
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
