#  Resgate Python Client

Resgate is a project, which gives microservices the ability to very easily provide a scalable and reliable websocket connection to the outside world
For more information take a look at the project page https://github.com/jirenius/resgate

Essentially, microservices will publish data updates to NATS message broker via a pub sub feed. Resgate acts as a gateway between NATS and a websocket interface. Clients can connect to the websocket url provided by resgate and subscribe to the microservices
channels that they are interested in. Scaling is easy. Just add more resgate and NATS server instances. 

![alt text](https://github.com/duffar12/ResgateClient/blob/master/resgate.png)

### Motivation and Design considerations
* I started building this for a project, but the requirements changed so as I'm not actively using this.
* Happy to add extra functionality on request.
* Personally, I love the idea of resgate, but I find the resgate client protocol a little clunky and difficult to work with. The only client library I could find was a javascript library and I don't have a  great knowledge of javascript. So here we are.
* This is a very light client and a lot of functionality has been left out. The idea was to simplify the process of connecting to websockets provided by resgate.
* If you are using resgate for anything more than a very simple pub-sub websocket connection, you will quickly outgrow this client. But it may give you a good starting base to better understand the protocol.
* This client is for websocket clients only. I haven't provided functionality for REST clients
* This client is designed to be very lightweight, leaving many design considerations up to the developer. For example, it doesn't provide any logging or exceptions etc


### Getting started
* Download and install NATS
* Download and install Resgate
* Start the NATS server
* Start the Resgate server
* run example_service.py
* run example_client.py

The example_service sets up a channel called news.today on NATS
* It publishes new data to this NATS channel every 3 seconds
* Note that behind the scenes it is actually publishing to a few different NATS channels. This is one of the things that I find clunky about it, which is why I want to abstract it away

The example_client subscribes to the news.today channel
* It receives a subscription confirmation
* Starts receiving updates
* Unsubscribes after receiving 3 messages
* The client prints out both the raw message received from resgate, and the parsed message returned by the resclient. That way you can decide, which you prefer

 
