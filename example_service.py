import asyncio
import json
from nats.aio.client import Client as NATS


loop = asyncio.get_event_loop()
count = 0
subscriptions = dict()

async def run(loop):
    ''' A very simple service, which serves the news.today channel

       Updates are sent to the channel every 3 seconds
       Clients can subscribe to the channel via websocket using the resclient as an interface
    '''
    nc = NATS()

    await nc.connect("nats://0.0.0.0:4222", loop=loop)

    async def update_news(loop):
        # send an update to the news.today channel every 3 seconds
        await asyncio.sleep(3)
        msg = {"message":"news today"}
        await nc.publish('event.news.today.change', json.dumps(msg).encode())
        loop.create_task(update_news(loop))

    async def subscription_handler(msg):
        newmsg = {"result":{"model": {"message": "Hello world"}}}
        await nc.publish(msg.reply, json.dumps(newmsg).encode())

    async def access_handler(msg):
        newmsg = {"result":{"get": True, "call": ""}}
        await nc.publish(msg.reply, json.dumps(newmsg).encode())

    async def change_publisher(msg):
       # msg = {"message":"helloworld"}
        await nc.publish('news.today.change', json.dumps(msg).encode())

    # Simple publisher and async subscriber via coroutine.
    await nc.subscribe("get.news.today", cb=subscription_handler)
    await nc.subscribe("access.news.today", cb=access_handler)
    await nc.subscribe("call.news.today.set", cb=change_publisher)
    await update_news(loop)


if __name__ == '__main__':
    loop.create_task(run(loop))
    loop.run_forever()
