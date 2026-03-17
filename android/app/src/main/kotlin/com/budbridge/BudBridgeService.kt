package com.budbridge

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import com.budbridge.Prefs.btDeviceAddress
import com.budbridge.Prefs.btDeviceName
import com.budbridge.Prefs.pcIp
import com.budbridge.Prefs.phonePort
import com.budbridge.Prefs.sharedSecret

private const val TAG = "BudBridge/Service"
private const val NOTIF_CHANNEL = "budbridge_main"
private const val NOTIF_ID = 1

class BudBridgeService : Service() {

    companion object {
        const val ACTION_CLAIM = "com.budbridge.ACTION_CLAIM"
        const val ACTION_STOP = "com.budbridge.ACTION_STOP"

        fun start(context: Context) {
            val intent = Intent(context, BudBridgeService::class.java)
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            val intent = Intent(context, BudBridgeService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }
    }

    private lateinit var btHandler: BluetoothHandler
    private lateinit var nsdHelper: NsdHelper
    private lateinit var handoffManager: HandoffManager
    private lateinit var httpServer: HttpServer
    private var wakeLock: PowerManager.WakeLock? = null

    // -------------------------------------------------------------------------
    // Lifecycle
    // -------------------------------------------------------------------------

    override fun onCreate() {
        super.onCreate()
        btHandler = BluetoothHandler(this)
        nsdHelper = NsdHelper(this)
        handoffManager = HandoffManager(this, btHandler, nsdHelper)

        createNotificationChannel()
        startForeground(NOTIF_ID, buildNotification("Ready — tap to claim audio"))

        val port = phonePort
        httpServer = HttpServer(
            port = port,
            btHandler = btHandler,
            getDeviceAddress = { btDeviceAddress },
            getDeviceName = { btDeviceName },
            getAllowedIp = { pcIp },
            getSharedSecret = { sharedSecret },
            onReleaseRequest = ::handleReleaseRequest,
        )
        httpServer.start()
        nsdHelper.startAdvertising(port)

        acquireWakeLock()
        Log.i(TAG, "BudBridgeService started on port $port")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CLAIM -> triggerClaim()
            ACTION_STOP -> stopSelf()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        httpServer.stop()
        nsdHelper.stopAll()
        wakeLock?.release()
        Log.i(TAG, "BudBridgeService stopped")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    // -------------------------------------------------------------------------
    // Handoff
    // -------------------------------------------------------------------------

    private fun triggerClaim() {
        updateNotification("Claiming audio...")
        handoffManager.claimToPhone { success, message ->
            val notifText = if (success) "Connected — $message" else "Failed — $message"
            updateNotification(notifText)
            Log.i(TAG, "Claim result: $message")
        }
    }

    private fun handleReleaseRequest(): Boolean {
        val wasConnected = btHandler.isConnected(btDeviceAddress)
        btHandler.disconnect(btDeviceAddress)
        updateNotification("Released to PC")
        return wasConnected
    }

    // -------------------------------------------------------------------------
    // Notification
    // -------------------------------------------------------------------------

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            NOTIF_CHANNEL,
            "BudBridge",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "BudBridge background service"
            setShowBadge(false)
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        val claimIntent = PendingIntent.getService(
            this, 0,
            Intent(this, BudBridgeService::class.java).apply { action = ACTION_CLAIM },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val openIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return Notification.Builder(this, NOTIF_CHANNEL)
            .setContentTitle("BudBridge")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_headphone)
            .setContentIntent(openIntent)
            .setOngoing(true)
            .addAction(
                Notification.Action.Builder(
                    null,
                    "Claim Audio",
                    claimIntent
                ).build()
            )
            .build()
    }

    private fun updateNotification(text: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIF_ID, buildNotification(text))
    }

    // -------------------------------------------------------------------------
    // Wake lock
    // -------------------------------------------------------------------------

    private fun acquireWakeLock() {
        wakeLock = (getSystemService(Context.POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "BudBridge:WakeLock")
            .also { it.acquire() }
    }
}
