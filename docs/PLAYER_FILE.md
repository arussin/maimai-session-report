# Bring your scores into maimai.party

[![maimai Session Report on GitHub](images/session-report-github.svg)](https://github.com/arussin/maimai-session-report)

If you use **Kamaitachi** to track your maimai DX scores, **maimai Session Report** can turn your play sessions into a report showing your scores, rating progress and practice targets. Start with the project on GitHub above, then follow the [Kamaitachi setup guide](https://github.com/arussin/maimai-session-report/blob/main/docs/KAMAITACHI.md) to create a report from your imported plays.

Once you have a report, you can bring its scores into maimai.party directly or download a **player file** to import later. Your best achievement, grade, chart rating, combo and sync badges, and saved history appear beside the charts you browse. You can also filter by several grades at once, achievement range, and other personal results.

## From a session report

Choose **Open in Party** below the maimai DX logo. A new tab shows the player's name, reconstructed rating and retained sessions. Choose **Import data** to bring that profile into maimai.party.

Nothing transfers just from opening a report. If you choose **Not now**, you can still browse the requested charts.

## Using a hosted report address

In Party builds with **Hosted Session Report**, paste your report's address and
confirm the profile. Direct import and remembered refresh require a public report
whose host explicitly allows Party to read its player export. Report owners can
enable this in the [installation settings](INSTALLATION.md#public-player-imports).

If **Open report** appears, open it, sign in if needed, and choose **Open in Party**,
or download a player file. Private reports use this consent-based transfer; they
do not support silent cross-site refresh. Remembered refresh reads exported data
and does not trigger a new score import at the report host.

## Using a player file

1. Choose **Download player file** in your report. On smaller screens, open **Export** first. It saves a file named `player.maimai.json.gz`; leave it compressed.
2. Open [maimai.party](https://maimai.party), then open the gear menu.
3. Choose **Import player data** and select that file.
4. Check the profile, then choose **Import data**.

The file and **Open in Party** bring over the same information. The file is useful if the direct transfer is blocked, or if you want to carry your data to another browser or device.

## Where your data stays

maimai.party reads the file in your browser. You do not need an account, and importing does not send your score records to a new server-side account.

Choose **Remember on this device** if you want your profile restored when you return. Otherwise it stays for the current tab session. The gear menu lets you **Hide player data** temporarily, or **Forget remembered player data**. Forgetting removes the saved copy; the current tab can keep displaying it until closed.

The small playercard in Settings shows which profile is active. Its rating is reconstructed from the available rating pools. A missing score means **No recorded PB**, not proof that you have never played the chart.

**Recorded plays** shows actual retained plays at their original play times. A score can be present in several reports without becoming several plays. Older report summaries are matched to their original score records only when the saved evidence identifies one source play unambiguously; distinct source score IDs are always preserved.

**Show saved PB changes** opens a separate list of changes to the saved best score. Unchanged snapshots are grouped. These dates describe when the PB was saved, not a session in which you played that song. A chart may have a saved PB and no retained play history.

## Keeping your file up to date

Download a file from a newer report, or open that report in Party again. For the same player, importing retains earlier history without duplicating source plays and keeps newer results. The same reconciliation applies when restoring a profile already saved in your browser. A different player's file switches profiles without combining their scores.

If you generate reports locally, add `--export-party-data` to maintain a reusable player file alongside the HTML report. For configuration and adding earlier captures, see the [setup and history guide](MAIMAI_PARTY.md#local-commands).

If an import fails, your existing usable data stays in place. Try downloading the file again, then importing it through Settings.
