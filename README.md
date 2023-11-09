# Exorde Swarm Client

...


## Running

The client is now structured as a swarm, as such there are two main possible way
to launch it:

    - managed
    - unmanaged

## Managed

Managed is the default way of running the client. The full configuration file
has been updated so you can tinker how many scraper / spotters are instanciated.

You can run this configuration from within a single container and the default
configuration should be sufficient.

## Un-managed

Un-managed means that every process is now controled by your own process manager
(k8, docker, supervisor, whatever suits you best)

The multi.py has a -cmd option which allows you to retrieve the command line
of the specific blade you want to run.

### With docker-compose

todo

# Topology

The orchestrator, spotter, scrapers are all mandatory to be able to run the 
exorde client, 

However,

you can now launch multiple scrapers on machine that do not have GPU capabilities
and the orchestrator will route their output to spotters that are specificaly
tailored for the task.

This means that you should be able to scale up the amount of scraper (to a point) 
independantly of GPU.

The orchestrator will randomize the target of the scrapers if you specify multiple.

> note that only instances of spotters are considered "nodes".
