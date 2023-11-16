# Live monitoring of the cluster

# Problem

Test the behavior of the client at run-time and alert annomalies.

# Solution

Consumes the logs of the cluster and interpret them.

# Implementation

Traditional logs allow us to read and review the behavior of software but are
not primarly designed for software consumption.

The strategy defined below is a take on how logs can be used as a framework for
monitoring, the intent is to create a simple state machine that can be mastered
and configured to alert users of malfunction.

> Note that this enforce a very specific methodology around logging.

## State

Each log is a considered a shard and is deep merged into a state.

```example
state = { } # init empty
> log({ 1: { 'foo': 'bar'} })
state = { 1: { 'foo': 'bar'} }
> log({ 2: 'bar', 1: { 'something': 'merged'} })
state = { 1: { 'foo': 'bar', 'something': 'merged' }, 2: 'bar' }
```

This allows us to design logging as a set of instructions and implement various
monitoring algorithm on the basis that those instruction follow a specific
logic.

## Example `Hello World`

Each blade start's by logging `Hello World`

> { 'blade_host_A': { 'msg': 'Hello World' } }
> { 'blade_host_B': { 'msg': 'Hello World' } }
{
    'blade_host_A': { 'msg': 'Hello World' },
    'blade_host_B': { 'msg': 'Hello World' } 
}

> note 'msg' is the default logging message, with this we won't be able to 
effectively test in time if a blade has specified 'hello world' in 'msg' 
because 'msg' is the default logging message which is overwritten on every log.

However we can test the presence of the nodes by inspecting the state's keys.

## Methodology & Idempotence

Avoiding key-conflicts creates a method for manipulating the state based on
instructions. Using a key-conflict allows us to manipulate existing values or
erase them.

## Testing goals

- Is the client currently running ?
    - are unit-live-test correct ?

## Benchmark goals

- What is the current's client's perf status ? 
    - Count the number of items collected by
        - scraper
        - spoter
    - Counter number of items sent trough

### Unit Live Testing

### Intent

> is blade's intent correctly changed ?
- orchestrator set's intent on module
`> { 'intents': { '<intent-id>': { 'host': 'blade_host' } } }`
- did the blade start scraping ?
```
> { 
    'intents': { 
        '<intent-id>': { 'resolution': { <scraper-host>: ...details } } 
    } 
  }
```
- is the blade sending items to the correct host ?
```
> { 
    'intents': { 
        '<intent-id>': { 'resolution': { <spotting-host>: ...details } } 
    } 
  }
```
Note that the resolution can be made by multiple hosts. For example for intents
we also want a receiving signal from the spotting blade, so we add the host key
in the resolution. So,

```
    !resolution => no answer

    and resolution.keys = hosts who answered 

    and 'scraper_host' in resolution.keys => 
        scraper started but no reveived data

    and 'spotter_host' in resolution.keys => 
        scrapper sends and spotter is receiving
```

Also note that even tough scraper and spotter are receiving this might not mean
that everything is running smoothly.

#### Module update
> did blade correctly change it's module version ?
- orchestrator set's intent with a new module
`> { 'intents': { '<intent-id>': { 'module' } } }`
- blade install new module
`> { 'intents': { '<intent-id>': { 'resolution': { <host>: ...details } } } }`

#### Start scraping
> did the blade start scrapping ?
- orchestrator set's intent to start scraping
`> { 'intents': { '<intent-id>': { 'module' } } }`


### Counting

If everything is running smoothly, the scraper should be able to resolve with
the following information.

```
    resolution[scraper_host] = {
        'item_scraped': {
            'domain': {
                'tries': ...,
                'time_spent': '...'
                'item_collected': '...',
                'item_sent_tries': '...',
                'item_sent': '...',
                'errors': []
            }
        }
    }
```

### Error Monitoring

The `monitor` is not a place to react to those situations as this is the
orchestrator's job. However, we should collect all errors and create a detailed
report of the situation.

### Note on Memory Management

We need to be able to remove keys in the state after a certain delay. But
doing so would also break the counting defined above.

Since we have multiprocessing AND asynchronicity involved, we cannot just set
values on specific keys to implement a counter logic as subcalls would erase
the previous value and loose context.

To implement a proper counter we need each count call to be preserved. This is
done by using a separate key for each blade and managing this problem at the
time of collapse. (todo, see counter CRDT)

### Logging aggregation details

Logging aggregation is provided both for docker and bare.

#### Bare

Bare logging aggregation is realised thanks to the /logs endpoint

#### Docker

Docker logging aggregation is realised using the docker api

##### Docker Commands Summary

###### Listen to Docker Events
```bash
curl --unix-socket /var/run/docker.sock http://localhost/events
```

###### Read Logs from a Specific Container
Replace `[CONTAINER_ID]` with the container's ID.
```bash
curl --unix-socket /var/run/docker.sock "http://localhost/containers/[CONTAINER_ID]/logs?stdout=1&stderr=1&follow=1"
```

###### Retrieve containers ID's we should read logs from

(List Containers Filtered Based on a Label)

Labels are used to identify containers to collect logs from

```bash
curl --unix-socket /var/run/docker.sock "http://localhost/containers/json?filters=$(echo -n '{"label": ["mylabel=myvalue"]}' | jq -sRr @uri)"
```

###### Adding a Label in Docker Compose


```yaml
version: '3'
services:
  myservice:
    image: myimage
    labels:
      mylabel: "myvalue"
    # ... other service configuration ...
```



