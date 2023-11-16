export default function connectWebSocket(setConnection, onNewMessage, host) {
    let socket = new WebSocket(host);
    // Handle incoming messages from the WebSocket server
    socket.addEventListener('message', (event) => {
        onNewMessage(event.data);
    });

    // Handle WebSocket connection open
    socket.addEventListener('open', (event) => {
        console.log('WebSocket connection opened');
        setConnection(true);
    });

    // Handle WebSocket connection close
    socket.addEventListener('close', (event) => {
        setConnection(false);
        if (event.wasClean) {
            console.log(`WebSocket connection closed cleanly, code=${event.code}, reason=${event.reason}`);
        } else {
            console.log('WebSocket connection abruptly closed');
        }

        // Retry the connection after a delay (5 seconds)
        setTimeout(connectWebSocket, 5000);
    });

    // Handle WebSocket errors
    socket.addEventListener('error', (error) => {
        console.log(`WebSocket error: ${error}`);
    });
}
