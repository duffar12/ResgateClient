import websocket
import json
import resclient


count = 0
def on_open(ws):
    print("opened")
    #subscribe to news.today channel
    msg = resclient.get_subscribe_msg('news.today')
    ws.send(json.dumps(msg))

def on_message(ws, message):
    global count
    count += 1
    print('message received from resgate server: ', message)
    msg = resclient.parse_message(json.loads(message))
    print('parsed message: ',msg)
    if count ==3 :
        print('unsubscribing')
        msg = resclient.get_unsubscribe_msg('news.today')
        ws.send(json.dumps(msg))

def on_error(ws, error):
    print('There was an error {}'.format(error))

def on_close(ws):
    print("closed")


if __name__ == '__main__':
    ws = websocket.WebSocketApp('ws://localhost:8080'
                                ,on_message = on_message
                                ,on_error = on_error
                                ,on_close = on_close
                                ,on_open=on_open)
    ws.run_forever()