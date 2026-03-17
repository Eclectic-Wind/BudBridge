package com.budbridge

import android.bluetooth.BluetoothA2dp
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothHeadset
import android.bluetooth.BluetoothProfile
import android.content.Context
import android.os.Build
import android.util.Log
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

private const val TAG = "BudBridge/BT"

class BluetoothHandler(private val context: Context) {

    private val adapter: BluetoothAdapter? = BluetoothAdapter.getDefaultAdapter()

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    /** All paired devices that support audio profiles. */
    fun pairedAudioDevices(): List<BluetoothDevice> {
        val a = adapter ?: return emptyList()
        return try {
            a.bondedDevices
                ?.filter { it.bluetoothClass?.hasService(android.bluetooth.BluetoothClass.Service.AUDIO) == true
                        || it.bluetoothClass?.majorDeviceClass == android.bluetooth.BluetoothClass.Device.Major.AUDIO_VIDEO }
                ?: emptyList()
        } catch (e: SecurityException) {
            Log.w(TAG, "pairedAudioDevices: permission denied", e)
            emptyList()
        }
    }

    /** True if the device with *address* is currently connected on A2DP. */
    fun isConnected(address: String): Boolean {
        val device = findDevice(address) ?: return false
        var result = false
        val latch = CountDownLatch(1)
        adapter?.getProfileProxy(context, object : BluetoothProfile.ServiceListener {
            override fun onServiceConnected(profile: Int, proxy: BluetoothProfile) {
                result = try {
                    proxy.connectedDevices.any { it.address == address }
                } catch (e: SecurityException) { false }
                adapter.closeProfileProxy(profile, proxy)
                latch.countDown()
            }
            override fun onServiceDisconnected(profile: Int) { latch.countDown() }
        }, BluetoothProfile.A2DP)
        latch.await(3, TimeUnit.SECONDS)
        return result
    }

    /** Connect A2DP (and HFP) for the device at *address*. Returns true if initiated. */
    fun connect(address: String): Boolean {
        val device = findDevice(address) ?: return false
        var ok = false
        val latch = CountDownLatch(1)
        adapter?.getProfileProxy(context, object : BluetoothProfile.ServiceListener {
            override fun onServiceConnected(profile: Int, proxy: BluetoothProfile) {
                ok = try {
                    when (proxy) {
                        is BluetoothA2dp -> invokeConnect(proxy, device)
                        else -> false
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "connect: $e")
                    false
                }
                adapter.closeProfileProxy(profile, proxy)
                latch.countDown()
            }
            override fun onServiceDisconnected(profile: Int) { latch.countDown() }
        }, BluetoothProfile.A2DP)
        latch.await(5, TimeUnit.SECONDS)

        // Also attempt HFP (hands-free) in the background — best effort
        adapter?.getProfileProxy(context, object : BluetoothProfile.ServiceListener {
            override fun onServiceConnected(profile: Int, proxy: BluetoothProfile) {
                try {
                    if (proxy is BluetoothHeadset) invokeConnect(proxy, device)
                } catch (_: Exception) {}
                adapter.closeProfileProxy(profile, proxy)
            }
            override fun onServiceDisconnected(profile: Int) {}
        }, BluetoothProfile.HEADSET)

        return ok
    }

    /** Disconnect A2DP (and HFP) for the device at *address*. Returns true if initiated. */
    fun disconnect(address: String): Boolean {
        val device = findDevice(address) ?: return false
        var ok = false
        val latch = CountDownLatch(1)
        adapter?.getProfileProxy(context, object : BluetoothProfile.ServiceListener {
            override fun onServiceConnected(profile: Int, proxy: BluetoothProfile) {
                ok = try {
                    when (proxy) {
                        is BluetoothA2dp -> invokeDisconnect(proxy, device)
                        else -> false
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "disconnect: $e")
                    false
                }
                adapter.closeProfileProxy(profile, proxy)
                latch.countDown()
            }
            override fun onServiceDisconnected(profile: Int) { latch.countDown() }
        }, BluetoothProfile.A2DP)
        latch.await(5, TimeUnit.SECONDS)

        // Also disconnect HFP
        adapter?.getProfileProxy(context, object : BluetoothProfile.ServiceListener {
            override fun onServiceConnected(profile: Int, proxy: BluetoothProfile) {
                try {
                    if (proxy is BluetoothHeadset) invokeDisconnect(proxy, device)
                } catch (_: Exception) {}
                adapter.closeProfileProxy(profile, proxy)
            }
            override fun onServiceDisconnected(profile: Int) {}
        }, BluetoothProfile.HEADSET)

        return ok
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private fun findDevice(address: String): BluetoothDevice? = try {
        adapter?.bondedDevices?.firstOrNull { it.address == address }
    } catch (e: SecurityException) { null }

    /** Call BluetoothA2dp/BluetoothHeadset.connect() via reflection (hidden API). */
    private fun invokeConnect(proxy: BluetoothProfile, device: BluetoothDevice): Boolean {
        return try {
            val method = proxy.javaClass.getMethod("connect", BluetoothDevice::class.java)
            method.invoke(proxy, device) as? Boolean ?: true
        } catch (e: Exception) {
            Log.w(TAG, "invokeConnect failed: $e")
            false
        }
    }

    private fun invokeDisconnect(proxy: BluetoothProfile, device: BluetoothDevice): Boolean {
        return try {
            val method = proxy.javaClass.getMethod("disconnect", BluetoothDevice::class.java)
            method.invoke(proxy, device) as? Boolean ?: true
        } catch (e: Exception) {
            Log.w(TAG, "invokeDisconnect failed: $e")
            false
        }
    }
}
