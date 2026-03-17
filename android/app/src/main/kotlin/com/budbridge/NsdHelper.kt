package com.budbridge

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.util.Log

private const val TAG = "BudBridge/NSD"
private const val SERVICE_TYPE = "_budbridge._tcp."
private const val SERVICE_NAME = "BudBridge-Phone"

/**
 * Handles mDNS advertisement (so the PC can find this phone automatically)
 * and PC discovery (so this phone knows the PC's current IP).
 */
class NsdHelper(private val context: Context) {

    private val nsdManager = context.getSystemService(Context.NSD_SERVICE) as NsdManager

    private var registrationListener: NsdManager.RegistrationListener? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private var resolveListener: NsdManager.ResolveListener? = null

    // -------------------------------------------------------------------------
    // Advertise this phone on the LAN
    // -------------------------------------------------------------------------

    fun startAdvertising(port: Int) {
        val info = NsdServiceInfo().apply {
            serviceName = SERVICE_NAME
            serviceType = SERVICE_TYPE
            setPort(port)
            setAttribute("role", "phone")
            setAttribute("version", "1.0")
        }

        registrationListener = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(info: NsdServiceInfo) {
                Log.i(TAG, "Advertising as ${info.serviceName}")
            }
            override fun onRegistrationFailed(info: NsdServiceInfo, code: Int) {
                Log.w(TAG, "Registration failed: $code")
            }
            override fun onServiceUnregistered(info: NsdServiceInfo) {
                Log.d(TAG, "Unregistered")
            }
            override fun onUnregistrationFailed(info: NsdServiceInfo, code: Int) {
                Log.w(TAG, "Unregistration failed: $code")
            }
        }

        try {
            nsdManager.registerService(info, NsdManager.PROTOCOL_DNS_SD, registrationListener)
        } catch (e: Exception) {
            Log.e(TAG, "startAdvertising failed: $e")
        }
    }

    fun stopAdvertising() {
        registrationListener?.let {
            try { nsdManager.unregisterService(it) } catch (_: Exception) {}
            registrationListener = null
        }
    }

    // -------------------------------------------------------------------------
    // Discover the PC on the LAN
    // -------------------------------------------------------------------------

    /**
     * Browse for a BudBridge PC instance. Calls [onFound] with (ip, port) when found.
     * [onNotFound] is called if discovery is stopped without finding a PC.
     */
    fun discoverPc(onFound: (String, Int) -> Unit, onNotFound: () -> Unit = {}) {
        stopDiscovery()

        discoveryListener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(regType: String) {
                Log.d(TAG, "Discovery started")
            }
            override fun onServiceFound(info: NsdServiceInfo) {
                if (info.serviceType.contains("_budbridge._tcp")) {
                    val rl = object : NsdManager.ResolveListener {
                        override fun onResolveFailed(i: NsdServiceInfo, code: Int) {
                            Log.w(TAG, "Resolve failed: $code")
                        }
                        override fun onServiceResolved(resolved: NsdServiceInfo) {
                            val role = resolved.attributes["role"]
                                ?.let { String(it) } ?: ""
                            if (role != "phone") {
                                // It's a PC instance
                                val ip = resolved.host?.hostAddress ?: return
                                val port = resolved.port
                                Log.i(TAG, "Found PC at $ip:$port")
                                onFound(ip, port)
                                stopDiscovery()
                            }
                        }
                    }
                    resolveListener = rl
                    try { nsdManager.resolveService(info, rl) } catch (e: Exception) {
                        Log.w(TAG, "resolveService failed: $e")
                    }
                }
            }
            override fun onServiceLost(info: NsdServiceInfo) {}
            override fun onDiscoveryStopped(regType: String) {}
            override fun onStartDiscoveryFailed(regType: String, code: Int) {
                Log.w(TAG, "Start discovery failed: $code")
                onNotFound()
            }
            override fun onStopDiscoveryFailed(regType: String, code: Int) {}
        }

        try {
            nsdManager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, discoveryListener)
        } catch (e: Exception) {
            Log.e(TAG, "discoverServices failed: $e")
            onNotFound()
        }
    }

    fun stopDiscovery() {
        discoveryListener?.let {
            try { nsdManager.stopServiceDiscovery(it) } catch (_: Exception) {}
            discoveryListener = null
        }
    }

    fun stopAll() {
        stopAdvertising()
        stopDiscovery()
    }
}
