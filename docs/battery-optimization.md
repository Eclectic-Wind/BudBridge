# Battery Optimization — Keeping Tasker Alive in the Background

Modern Android aggressively kills background apps to save battery. For BudBridge to work, Tasker **must** be able to run its HTTP server continuously. This guide explains how to disable battery restrictions for Tasker on every major Android OEM.

> **Also see:** [Don't Kill My App](https://dontkillmyapp.com/) — a comprehensive database of OEM-specific background restrictions and how to disable them.

---

## Why This Matters

If Tasker is battery-optimized, Android will:
- Kill the Tasker process after ~5–15 minutes of screen-off time
- Stop the HTTP server from responding
- Cause BudBridge on PC to report "Could not reach phone"

The fix is always the same concept: tell the system Tasker is **unrestricted** or **not optimizable**.

---

## Stock Android / Google Pixel

Stock Android follows the standard `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` pattern. Google Pixel devices are the most permissive.

**Steps:**

1. Open **Settings**
2. Tap **Apps**
3. Tap **See all apps**
4. Scroll to and tap **Tasker**
5. Tap **Battery**
6. Select **Unrestricted**
   > "Allow battery use in background without restrictions"

**Additionally (Pixel 6+):**

1. Open **Settings → Battery → Battery Saver**
2. Ensure Adaptive Battery is not restricting Tasker:
   - **Settings → Battery → Adaptive Battery** → OFF (optional, system-wide)

---

## Samsung One UI (Galaxy S/A/Z series)

Samsung has multiple layers of battery management: the standard Android restriction plus Samsung's own "Sleeping apps" and "Deep sleeping apps" systems.

### Step 1: Standard Battery Optimization

1. Open **Settings**
2. Tap **Apps** (or **Application Manager**)
3. Tap the three-dot menu → **Special access**
4. Tap **Optimize battery usage**
5. In the dropdown, switch from "Apps not optimized" to **All**
6. Find **Tasker** and toggle it **OFF** (not optimized)

### Step 2: Remove from Sleeping Apps

1. Open **Settings → Battery and device care → Battery**
2. Tap **Background usage limits**
3. Check **Sleeping apps** and **Deep sleeping apps**
4. If Tasker appears in either list, swipe it left to remove it

### Step 3: Allow Background Activity

1. Open **Settings → Apps → Tasker**
2. Tap **Battery**
3. Select **Unrestricted**

### Step 4: Disable Adaptive Battery (optional)

1. **Settings → Battery and device care → Battery**
2. Tap **More battery settings**
3. Toggle **Adaptive battery** → OFF

> **Note for One UI 6+:** Samsung moved some settings. Look under **Settings → Battery → Background usage limits** if you can't find the above.

---

## OnePlus / OxygenOS (and ColorOS-based OnePlus)

OnePlus uses aggressive background management through "Battery Optimization" and "Auto-launch" settings.

### Step 1: Battery Optimization

1. Open **Settings**
2. Tap **Battery** → **Battery optimization**
3. Tap the dropdown → **All apps**
4. Find and tap **Tasker**
5. Select **Don't optimize** → **Done**

### Step 2: Allow Auto-launch

1. Open **Settings → Apps → App management**
2. Tap **Tasker**
3. Tap **Auto launch** → Enable **Allow auto launch**

### Step 3: Allow Background Activity

1. In **Settings → Apps → Tasker → Battery**
2. Enable **Allow background activity**

### Step 4: Advanced Optimization (OxygenOS 13+)

1. **Settings → Battery → More settings → Battery optimization**
2. Find Tasker → **Don't optimize**
3. Also check: **Settings → Privacy → Permission manager** → verify Tasker has needed permissions

---

## Xiaomi / MIUI / HyperOS (Redmi, POCO, Xiaomi)

Xiaomi/MIUI is notorious for killing background apps. Multiple steps are required.

### Step 1: Battery Saver Exclusion

1. Open **Settings**
2. Tap **Apps**
3. Tap **Manage apps**
4. Find and tap **Tasker**
5. Tap **Battery saver**
6. Select **No restrictions**

### Step 2: Autostart

1. Open **Settings → Apps → Manage apps → Tasker**
2. Tap **Autostart** → Enable it (toggle ON)

### Step 3: Battery Optimization (Android-level)

1. Open **Settings → Battery & performance**
2. Tap **Choose apps** (or scroll to "Battery optimization")
3. Find Tasker → set to **No restrictions**

### Step 4: MIUI App Lock (prevent being killed by memory cleaner)

1. Open the **Recent Apps** screen (square button or swipe up and hold)
2. Find Tasker
3. **Long-press** the Tasker card
4. Tap the **lock icon** (🔒) to lock it in memory

### Step 5: Disable MIUI Optimization (developer option — last resort)

1. Enable **Developer Options** (tap Build Number 7 times in Settings → About phone)
2. Go to **Settings → Additional Settings → Developer Options**
3. Scroll down and toggle **MIUI Optimization** → OFF
4. Reboot

> **HyperOS (MIUI 15+):** Steps are similar. Look under **Settings → Apps → Tasker → Battery usage** and set to **Unrestricted**.

---

## Oppo / ColorOS (Oppo, Realme)

ColorOS has its own layer of process management on top of Android's.

### Step 1: Battery Optimization

1. Open **Settings**
2. Tap **Battery** → **Battery optimization**
3. Tap the dropdown → **All apps**
4. Find and tap **Tasker**
5. Select **Don't optimize**

### Step 2: Auto-launch / Freeze on Close

1. Open **Settings → Apps → App management → Tasker**
2. Look for **Freeze app when closed** or **Auto-launch** → Disable freezing, Enable auto-launch

### Step 3: High Background Activity

1. **Settings → Battery → More settings**
2. Find **Tasker** → Allow **High background activity**

### Step 4: Allow Startup (ColorOS 14+)

1. **Settings → Privacy → Special app access → Autostart**
2. Enable Tasker

---

## Huawei / EMUI / HarmonyOS

Huawei's power management is extremely aggressive, especially on EMUI 9+ and HarmonyOS 2+.

### Step 1: Protected Apps / App Launch

1. Open **Settings**
2. Tap **Apps & notifications** → **App launch**
3. Find **Tasker**
4. Toggle it from "Automatic" to **Manual**
5. In the popup, enable all three:
   - **Auto-launch**
   - **Secondary launch** (allow other apps to start Tasker)
   - **Run in background**

### Step 2: Battery Optimization

1. Open **Settings → Battery → App battery usage**
   (or **Settings → Battery → Launch apps**)
2. Find Tasker
3. Set to **Don't optimize** or disable all restrictions

### Step 3: Disable Power-intensive App Prompt

1. **Settings → Battery**
2. Tap **Power-intensive apps** (or "High power consumption")
3. If Tasker is listed, remove it from the list

### Step 4: Background App Refresh

1. **Settings → Apps → Tasker → Battery**
2. Enable **Run in background**
3. Set **Background activity** to **Unrestricted**

> **Note:** On HarmonyOS 4+, the path may be **Settings → Apps → Tasker → Battery usage** → **Unrestricted**.

---

## Sony Xperia

Sony's STAMINA mode and Adaptive Battery can interrupt Tasker.

### Step 1: STAMINA Mode Exception

1. Open **Settings**
2. Tap **Battery**
3. Tap **STAMINA mode** → tap **Exceptions**
4. Add **Tasker** to the exceptions list

### Step 2: Standard Battery Optimization

1. **Settings → Battery → Battery optimization**
2. Switch to **All apps**
3. Find Tasker → **Don't optimize**

### Step 3: Background Data

1. **Settings → Network & internet → Data usage**
2. Tap **Data saver** (if enabled)
3. Add Tasker to **Unrestricted apps**

---

## Motorola (Stock-ish Android)

Motorola is generally close to stock Android but has some extras.

### Step 1: Battery Optimization

1. Open **Settings**
2. Tap **Battery** → **Battery optimization**
3. Tap dropdown → **All apps**
4. Find and tap **Tasker**
5. Select **Don't optimize**

### Step 2: Moto Actions Background

1. **Settings → Apps → Tasker → Battery**
2. Set to **Unrestricted**

### Step 3: Adaptive Battery

1. **Settings → Battery → Adaptive Battery**
2. Ensure Tasker is not listed as a restricted app
3. Optionally disable Adaptive Battery system-wide

---

## Universal Fallback: Android Accessibility & Notification Access

Some Tasker features (and keeping it alive) benefit from these permissions:

1. **Settings → Accessibility → Tasker** → Enable
2. **Settings → Apps → Special app access → Notification access → Tasker** → Enable
3. **Settings → Apps → Special app access → Device admin apps → Tasker** → Enable (if prompted)

---

## Verifying Tasker Stays Alive

After configuring battery settings:

1. Start the **BB HTTP Server** profile in Tasker
2. Lock your phone screen and wait 5–10 minutes
3. From your PC, run:
   ```bash
   curl http://<phone-ip>:8521/ping
   ```
4. If you get a response, Tasker is alive in the background
5. If not, try the steps for your OEM again, or check dontkillmyapp.com

---

## Resources

- **Don't Kill My App:** https://dontkillmyapp.com/
  The most comprehensive guide to per-OEM background restrictions, updated regularly.

- **Tasker FAQ:** https://tasker.joaoapps.com/faq.html

- **BudBridge Troubleshooting:** [troubleshooting.md](troubleshooting.md)
