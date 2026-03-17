package com.budbridge

import android.util.Log
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

private const val TAG = "BudBridge/HTTP"

/**
 * Minimal HTTP/1.1 server built on ServerSocket — no external dependencies.
 * Handles GET /ping, GET /status, POST /release.
 */
class HttpServer(
    private val port: Int,
    private val btHandler: BluetoothHandler,
    private val getDeviceAddress: () -> String,
    private val getDeviceName: () -> String,
    private val getAllowedIp: () -> String,       // phone only accepts requests from the PC IP
    private val getSharedSecret: () -> String,
    private val onReleaseRequest: () -> Boolean,  // returns was_connected
) {
    private val running = AtomicBoolean(false)
    private val pool = Executors.newCachedThreadPool()
    private var serverSocket: ServerSocket? = null

    fun start() {
        if (running.getAndSet(true)) return
        pool.submit {
            try {
                serverSocket = ServerSocket(port)
                Log.i(TAG, "HTTP server listening on port $port")
                while (running.get()) {
                    val client = serverSocket!!.accept()
                    pool.submit { handle(client) }
                }
            } catch (e: Exception) {
                if (running.get()) Log.e(TAG, "Server error: $e")
            }
        }
    }

    fun stop() {
        running.set(false)
        try { serverSocket?.close() } catch (_: Exception) {}
    }

    // -------------------------------------------------------------------------
    // Request handling
    // -------------------------------------------------------------------------

    private fun handle(socket: Socket) {
        try {
            socket.use {
                val reader = BufferedReader(InputStreamReader(it.getInputStream()))
                val writer = PrintWriter(it.getOutputStream(), true)

                // Read request line
                val requestLine = reader.readLine() ?: return
                val parts = requestLine.split(" ")
                if (parts.size < 2) return
                val method = parts[0]
                val path = parts[1].substringBefore("?")

                // Read headers
                val headers = mutableMapOf<String, String>()
                var line: String?
                while (reader.readLine().also { line = it } != null && line!!.isNotEmpty()) {
                    val colon = line!!.indexOf(':')
                    if (colon > 0) {
                        headers[line!!.substring(0, colon).trim().lowercase()] =
                            line!!.substring(colon + 1).trim()
                    }
                }

                // IP allowlist check
                val remoteIp = socket.inetAddress.hostAddress ?: ""
                val allowedIp = getAllowedIp()
                if (allowedIp.isNotEmpty() && remoteIp != allowedIp && remoteIp != "127.0.0.1") {
                    respond(writer, 403, jsonError("unauthorized", "Request from unauthorized source"))
                    Log.w(TAG, "Rejected request from $remoteIp (expected $allowedIp)")
                    return
                }

                // Shared secret check
                val secret = getSharedSecret()
                if (secret.isNotEmpty()) {
                    val token = headers["x-budbridge-token"] ?: ""
                    if (token != secret) {
                        respond(writer, 403, jsonError("unauthorized", "Invalid token"))
                        return
                    }
                }

                // Route
                when {
                    method == "GET" && path == "/ping" -> {
                        respond(writer, 200, """{"alive":true,"app":"BudBridge","version":"1.0"}""")
                    }
                    method == "GET" && path == "/status" -> {
                        val connected = btHandler.isConnected(getDeviceAddress())
                        respond(writer, 200, """{"connected":$connected,"device":"${getDeviceName()}"}""")
                    }
                    method == "POST" && path == "/release" -> {
                        val wasConnected = onReleaseRequest()
                        respond(writer, 200, """{"released":true,"was_connected":$wasConnected}""")
                    }
                    else -> {
                        respond(writer, 404, jsonError("not_found", "Unknown path: $path"))
                    }
                }
            }
        } catch (e: Exception) {
            Log.d(TAG, "handle: $e")
        }
    }

    private fun respond(writer: PrintWriter, status: Int, body: String) {
        val statusText = when (status) {
            200 -> "OK"; 403 -> "Forbidden"; 404 -> "Not Found"
            409 -> "Conflict"; 500 -> "Internal Server Error"; else -> "Unknown"
        }
        writer.print("HTTP/1.1 $status $statusText\r\n")
        writer.print("Content-Type: application/json\r\n")
        writer.print("Content-Length: ${body.toByteArray().size}\r\n")
        writer.print("Connection: close\r\n")
        writer.print("\r\n")
        writer.print(body)
        writer.flush()
    }

    private fun jsonError(code: String, message: String) =
        """{"error":"$code","message":"$message"}"""
}
