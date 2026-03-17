package com.budbridge

import android.content.Context
import android.util.Log
import com.budbridge.Prefs.btDeviceAddress
import com.budbridge.Prefs.btDeviceName
import com.budbridge.Prefs.pcIp
import com.budbridge.Prefs.pcPort
import com.budbridge.Prefs.sharedSecret
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.atomic.AtomicBoolean

private const val TAG = "BudBridge/Handoff"

/**
 * Orchestrates claiming audio to the phone:
 * 1. POST /release to the PC
 * 2. Wait for BT device to become available
 * 3. Connect BT on the phone
 */
class HandoffManager(
    private val context: Context,
    private val btHandler: BluetoothHandler,
    private val nsdHelper: NsdHelper,
) {
    val inProgress = AtomicBoolean(false)

    fun claimToPhone(onResult: (success: Boolean, message: String) -> Unit) {
        if (!inProgress.compareAndSet(false, true)) {
            onResult(false, "Handoff already in progress")
            return
        }

        Thread {
            try {
                val address = context.btDeviceAddress
                val name = context.btDeviceName

                // Step 1: Tell PC to release — resolve IP via mDNS first, fallback to stored
                val pcReleased = tellPcRelease()

                if (!pcReleased) {
                    Log.w(TAG, "PC unreachable — attempting direct BT connect anyway")
                }

                // Step 2: Wait for device to become available
                Thread.sleep(if (pcReleased) 2500L else 500L)

                // Step 3: Connect BT
                val connected = btHandler.connect(address)
                if (connected) {
                    // Give the stack a moment to fully connect
                    Thread.sleep(1500)
                    onResult(true, "Connected to $name")
                } else {
                    // Retry once
                    Thread.sleep(2000)
                    val retry = btHandler.connect(address)
                    Thread.sleep(1500)
                    onResult(retry, if (retry) "Connected to $name (retry)" else "Could not connect to $name")
                }
            } catch (e: Exception) {
                Log.e(TAG, "claimToPhone: $e")
                onResult(false, "Error: ${e.message}")
            } finally {
                inProgress.set(false)
            }
        }.start()
    }

    // -------------------------------------------------------------------------
    // Internal
    // -------------------------------------------------------------------------

    private fun tellPcRelease(): Boolean {
        // Resolve PC IP: use stored if present, otherwise try mDNS on demand
        var ip = context.pcIp
        val port = context.pcPort

        if (ip.isEmpty()) {
            ip = resolvePcViaMdns() ?: return false
        }

        return try {
            val url = URL("http://$ip:$port/release")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.connectTimeout = 3000
            conn.readTimeout = 5000
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("Content-Length", "0")
            val secret = context.sharedSecret
            if (secret.isNotEmpty()) conn.setRequestProperty("X-BudBridge-Token", secret)
            conn.doOutput = true
            conn.outputStream.close()
            val code = conn.responseCode
            conn.disconnect()
            Log.i(TAG, "PC /release → HTTP $code")
            code == 200
        } catch (e: Exception) {
            Log.w(TAG, "tellPcRelease failed: $e")
            false
        }
    }

    private fun resolvePcViaMdns(): String? {
        var result: String? = null
        val latch = java.util.concurrent.CountDownLatch(1)
        nsdHelper.discoverPc(
            onFound = { ip, port ->
                context.pcIp = ip
                context.pcPort = port
                result = ip
                latch.countDown()
            },
            onNotFound = { latch.countDown() }
        )
        latch.await(5, java.util.concurrent.TimeUnit.SECONDS)
        nsdHelper.stopDiscovery()
        return result
    }
}
