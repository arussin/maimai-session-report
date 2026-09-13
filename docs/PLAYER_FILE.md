# Bring your scores into maimai.party

A **player file** lets maimai.party show your own scores while you browse charts. You can see your best achievement, grade, chart rating, combo and sync badges, and any history kept by Session Report. You can also filter by several grades at once, achievement range, and other personal results.

## From a session report

Choose **Open in Party** below the maimai DX logo. A new tab shows the player's name, reconstructed rating and retained sessions. Choose **Import data** to bring that profile into maimai.party.

Nothing transfers just from opening a report. If you choose **Not now**, you can still browse the requested charts.

## Using a player file

1. Choose **Download player file** in your report. It saves a file named `player.maimai.json.gz`; leave it compressed.
2. Open [maimai.party](https://maimai.party), then open the gear menu.
3. Choose **Import player data** and select that file.
4. Check the profile, then choose **Import data**.

The file and **Open in Party** bring over the same information. The file is useful if the direct transfer is blocked, or if you want to carry your data to another browser or device.

## Where your data stays

maimai.party reads the file in your browser. You do not need an account, and importing does not send your score records to a new server-side account.

Choose **Remember on this device** if you want your profile restored when you return. Otherwise it stays for the current tab session. The gear menu lets you **Hide player data** temporarily, or **Forget remembered player data**. Forgetting removes the saved copy; the current tab can keep displaying it until closed.

The small playercard in Settings shows which profile is active. Its rating is reconstructed from the available rating pools. A missing score means **No recorded PB**, not proof that you have never played the chart. History includes only what your report has retained; a PB captured on a date is an observation, not an extra play.

## Keeping your file up to date

Download a file from a newer report, or open that report in Party again. For the same player, importing retains earlier history without duplicating source plays and keeps newer results. A different player's file switches profiles without combining their scores.

If you generate reports locally, add `--export-party-data` to maintain a reusable player file alongside the HTML report. For configuration and adding earlier captures, see the [setup and history guide](MAIMAI_PARTY.md#local-commands).

If an import fails, your existing usable data stays in place. Try downloading the file again, then importing it through Settings.
