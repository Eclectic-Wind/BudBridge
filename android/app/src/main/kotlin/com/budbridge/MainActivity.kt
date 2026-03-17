package com.budbridge

import android.Manifest
import android.bluetooth.BluetoothDevice
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.budbridge.Prefs.btDeviceAddress
import com.budbridge.Prefs.btDeviceName
import com.budbridge.Prefs.isConfigured
import com.budbridge.Prefs.pcIp
import com.budbridge.Prefs.pcPort
import com.budbridge.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var btHandler: BluetoothHandler
    private lateinit var nsdHelper: NsdHelper

    private val pairedDevices = mutableListOf<BluetoothDevice>()

    companion object {
        private const val REQ_PERMISSIONS = 100
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        btHandler = BluetoothHandler(this)
        nsdHelper = NsdHelper(this)

        if (isConfigured()) {
            showStatusScreen()
        } else {
            showSetupStep1()
        }
    }

    // -------------------------------------------------------------------------
    // Setup wizard
    // -------------------------------------------------------------------------

    private fun showSetupStep1() {
        hideAll()
        binding.layoutSetup1.visibility = View.VISIBLE
        binding.btnGrantPermissions.setOnClickListener { requestRequiredPermissions() }
    }

    private fun requestRequiredPermissions() {
        val perms = buildList {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                add(Manifest.permission.BLUETOOTH_CONNECT)
                add(Manifest.permission.BLUETOOTH_SCAN)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
        val missing = perms.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isEmpty()) {
            onPermissionsGranted()
        } else {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), REQ_PERMISSIONS)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_PERMISSIONS) {
            if (grantResults.all { it == PackageManager.PERMISSION_GRANTED }) {
                onPermissionsGranted()
            } else {
                Toast.makeText(this, "Permissions are required for BudBridge to work", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun onPermissionsGranted() {
        showSetupStep2()
    }

    private fun showSetupStep2() {
        hideAll()
        binding.layoutSetup2.visibility = View.VISIBLE

        // Populate the list of paired audio devices
        pairedDevices.clear()
        pairedDevices.addAll(btHandler.pairedAudioDevices())

        if (pairedDevices.isEmpty()) {
            binding.tvNoDevices.visibility = View.VISIBLE
            binding.deviceList.visibility = View.GONE
        } else {
            binding.tvNoDevices.visibility = View.GONE
            binding.deviceList.visibility = View.VISIBLE

            val names = pairedDevices.map { it.name ?: it.address }.toTypedArray()
            binding.deviceList.adapter = android.widget.ArrayAdapter(
                this, android.R.layout.simple_list_item_1, names
            )
            binding.deviceList.setOnItemClickListener { _, _, pos, _ ->
                val device = pairedDevices[pos]
                btDeviceAddress = device.address
                btDeviceName = device.name ?: device.address
                showSetupStep3()
            }
        }
    }

    private fun showSetupStep3() {
        hideAll()
        binding.layoutSetup3.visibility = View.VISIBLE
        binding.tvDiscoveryStatus.text = "Looking for BudBridge on your PC…"
        binding.progressDiscovery.visibility = View.VISIBLE
        binding.btnSkipDiscovery.visibility = View.VISIBLE

        binding.btnSkipDiscovery.setOnClickListener { finishSetup() }

        nsdHelper.discoverPc(
            onFound = { ip, port ->
                pcIp = ip
                pcPort = port
                runOnUiThread {
                    binding.tvDiscoveryStatus.text = "Found PC at $ip — you're all set!"
                    binding.progressDiscovery.visibility = View.GONE
                    binding.btnSkipDiscovery.text = "Continue"
                    binding.btnSkipDiscovery.setOnClickListener { finishSetup() }
                }
            },
            onNotFound = {
                runOnUiThread {
                    binding.tvDiscoveryStatus.text =
                        "PC not found automatically.\nMake sure BudBridge is running on your PC and both devices are on the same WiFi."
                    binding.progressDiscovery.visibility = View.GONE
                }
            }
        )
    }

    private fun finishSetup() {
        nsdHelper.stopDiscovery()
        BudBridgeService.start(this)
        showStatusScreen()
    }

    // -------------------------------------------------------------------------
    // Status screen (shown when already configured)
    // -------------------------------------------------------------------------

    private fun showStatusScreen() {
        hideAll()
        binding.layoutStatus.visibility = View.VISIBLE
        binding.tvStatusDevice.text = btDeviceName
        binding.tvStatusPc.text = if (pcIp.isEmpty()) "Not discovered yet" else pcIp

        binding.btnClaimNow.setOnClickListener {
            BudBridgeService.start(this)
            val intent = android.content.Intent(this, BudBridgeService::class.java).apply {
                action = BudBridgeService.ACTION_CLAIM
            }
            startService(intent)
            Toast.makeText(this, "Claiming audio…", Toast.LENGTH_SHORT).show()
        }

        binding.btnResetSetup.setOnClickListener {
            btDeviceName = ""
            btDeviceAddress = ""
            pcIp = ""
            BudBridgeService.stop(this)
            showSetupStep1()
        }
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private fun hideAll() {
        binding.layoutSetup1.visibility = View.GONE
        binding.layoutSetup2.visibility = View.GONE
        binding.layoutSetup3.visibility = View.GONE
        binding.layoutStatus.visibility = View.GONE
    }

    override fun onDestroy() {
        nsdHelper.stopAll()
        super.onDestroy()
    }
}
