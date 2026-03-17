package com.budbridge

import android.content.Context
import android.content.SharedPreferences

object Prefs {
    private const val NAME = "budbridge"

    private fun prefs(ctx: Context): SharedPreferences =
        ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE)

    var Context.btDeviceName: String
        get() = prefs(this).getString("bt_device_name", "") ?: ""
        set(v) { prefs(this).edit().putString("bt_device_name", v).apply() }

    var Context.btDeviceAddress: String
        get() = prefs(this).getString("bt_device_address", "") ?: ""
        set(v) { prefs(this).edit().putString("bt_device_address", v).apply() }

    // Discovered PC address — empty means not yet found
    var Context.pcIp: String
        get() = prefs(this).getString("pc_ip", "") ?: ""
        set(v) { prefs(this).edit().putString("pc_ip", v).apply() }

    var Context.pcPort: Int
        get() = prefs(this).getInt("pc_port", 8522)
        set(v) { prefs(this).edit().putInt("pc_port", v).apply() }

    var Context.phonePort: Int
        get() = prefs(this).getInt("phone_port", 8521)
        set(v) { prefs(this).edit().putInt("phone_port", v).apply() }

    var Context.sharedSecret: String
        get() = prefs(this).getString("shared_secret", "") ?: ""
        set(v) { prefs(this).edit().putString("shared_secret", v).apply() }

    fun Context.isConfigured(): Boolean =
        btDeviceAddress.isNotEmpty() && btDeviceName.isNotEmpty()
}
