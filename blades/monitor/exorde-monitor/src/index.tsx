import { render } from 'preact';
import { LocationProvider, Router, Route } from 'preact-iso';
import { useState } from 'preact/hooks';
import { merge } from 'lodash';

import { Header } from './components/Header.jsx';
import { Home } from './pages/Home/index.jsx';
import { State } from './pages/State/index.jsx';
import { NotFound } from './pages/_404.jsx';
import connectWebSocket from './components/Connection.jsx';

import './style.css';


export function App() {
    const [connected, setConnected] = useState(false);
    const [logState, setLogState] = useState({})

    const pushLog = (message: string) => setLogState(
        merge(logState, JSON.parse(message))
    )
    // const host = 'wss://' + window.location.host + '/ws';
    const host = 'wss://localhost:8004/ws';
    connectWebSocket(setConnected, pushLog, host)

	return (
		<LocationProvider>
			<Header connected={connected} />
			<main>
				<Router>
					<Route path="/" component={Home} />
					<Route path="/state" component={State} logState={logState} />
					<Route default component={NotFound} />
				</Router>
			</main>
		</LocationProvider>
	);
}

render(<App />, document.getElementById('app'));
