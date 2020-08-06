from tls_message import TLS_Message
from tls_message_packer import TLS_Message_Packer
from http_response import Http_Response
import socket
from key_generator import Key_Generator
from tls_connection import TLS_Connection

# HOST = 'github.com'
HOST = 'example.com'
PORT = 443

tls_connection = TLS_Connection()

with socket.create_connection((HOST, PORT)) as sock:
    # construct a Client Hello handshake message
    # TLS 1.0 protocol version for interoperability with earlier implementations
    tls_message = TLS_Message("handshake", "tls1.0")
    tls_message.set_handshake_type("Client_Hello")

    tls_connection.session = tls_message.session
    
    # Because middleboxes have been created and widely deployed that do not allow protocol versions that they do not recognize, 
    # the TLS 1.3 session must be disguised as a TLS 1.2 session. This field is no longer used for version negotiation and is hardcoded to the 1.2 version. 
    # Instead version negotiation is performed using the "Supported Versions" extension.
    tls_message.set_handshake_version("tls1.2")
    tls_message.server_name = HOST
    tls_message.generate_random()
    tls_message.add_cipher("TLS_AES_128_GCM_SHA256")
    tls_message.add_signature_hash_algorithm("ecdsa_secp256r1_sha256")
    tls_message.add_signature_hash_algorithm("ecdsa_secp384r1_sha384")
    tls_message.add_signature_hash_algorithm("ecdsa_secp521r1_sha512")
    tls_message.add_signature_hash_algorithm("ed25519")
    tls_message.add_signature_hash_algorithm("ed448")
    tls_message.add_signature_hash_algorithm("rsa_pss_pss_sha256")
    tls_message.add_signature_hash_algorithm("rsa_pss_pss_sha384")
    tls_message.add_signature_hash_algorithm("rsa_pss_pss_sha512")
    tls_message.add_signature_hash_algorithm("rsa_pss_rsae_sha256")
    tls_message.add_signature_hash_algorithm("rsa_pss_rsae_sha384")
    tls_message.add_signature_hash_algorithm("rsa_pss_rsae_sha512")
    tls_message.add_supported_group("secp256r1")
    tls_message.add_supported_group("x25519")
    tls_message.add_supported_version("tls1.3")
    client_private_key, client_public_key = Key_Generator.generate_x25519_keys()
    client_private_key, client_public_key = Key_Generator.generate_secp256r1_keys()
    tls_connection.client_private_key = client_private_key
    tls_connection.client_public_key = client_public_key
    tls_connection.server_public_key = None
    tls_message.add_public_key(client_public_key, "secp256r1")
    # pack the request and send
    packed = TLS_Message_Packer.pack(tls_message)
    print("SENDING: 📤")
    print(packed)
    sock.send(packed)

    while True:
        server_response = TLS_Message.receive(sock)
        if tls_connection.session != server_response.session:
            raise Exception("Session id doesn't match!")
        print("RECEIVED: 📥")
        # change_cipher_spec (x14/20)
        if server_response.message_type == b"\x14":
            print("Change Cipher Spec")
        # alert (x15/21)
        if server_response.message_type == b"\x15":
            print("Alert")
            # parse back the binary value to the string value so we can print it 
            level_message = list(TLS_Message.ALERT_LEVEL.keys())[list(TLS_Message.ALERT_LEVEL.values()).index(server_response.level.to_bytes(1, TLS_Message.ENDINESS))]
            description_message = list(TLS_Message.ALERT_DESCRIPTION.keys())[list(TLS_Message.ALERT_DESCRIPTION.values()).index(server_response.description.to_bytes(1, TLS_Message.ENDINESS))]
            print("Level: {}, Description: {}".format(level_message, description_message))
            break
        # handshake (x16/22)
        if server_response.message_type == b"\x16":
            print("Handshake")
            # if the response is a HelloRetryRequest this means the server is able to find an acceptable set of parameters but the ClientHello does not contain sufficient information to proceed with the handshake
            # it's kinda vague, but if the server handshake message doesn't contain a key exchange it's probably a Hello_Retry_Request
            if server_response.key_exchange is not None:
                print("Server_Hello")
                # retrieve information about the connection from the Server_Hello
                tls_connection.server_public_key = server_response.key_exchange
                # the crypthographic group(curve) to use
                tls_connection.cryptographic_group = server_response.supported_group
                # the cipher suite to use
                tls_connection.cipher_suite = server_response.cipher_suite
                # the TLS version to use
                tls_connection.tls_version = server_response.supported_version
                # -> this might be followed by a change cipher spec
                # -> all following messages afterwards are application data message (x17)
                # -> client can also send application data messages (x17) to the server
            else:
                print("Hello_Retry_Request")
                # -> client must response with a new Client_Hello with same session id, but changed key_share based on content of Hello_Retry_Request
                # (this probably means generating a new key with a different algorithm)
                # -> next response should be a Server_Hello message
                # for now print the expected curve and quit
                print("Expected curve: {}".format(server_response.supported_group))
                break
        # application_data (x17/23)
        if server_response.message_type == b"\x17":
            print("Application Data")
            msg = tls_connection.decode(server_response.application_data)
            print(msg)
