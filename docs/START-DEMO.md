# How to start the website (simple version)

The website is running **on your laptop**. When the laptop is off, the website is
off. To bring it back, you do **one thing**:

## 1. Open the project folder

`C:\Users\Admin\Desktop\BOARDING HOUSE INFO MANAGEMENT SYSTEMS`

## 2. Double-click `start-public-demo.bat`

That's it. A black window opens. It starts the database, starts the server, and
creates the public link by itself.

## 3. Wait for the line that says LIVE

About 10 seconds. You will see:

```
  mysql     starting it for you ...
  mysql     up
  LIVE  https://something-something.trycloudflare.com
  public check: 200 OK
```

The link on the **LIVE** line is your website address.

## 4. Copy the link

You don't need to select it — it is already copied to your clipboard. Paste it in
Messenger, in a browser, or wherever you need it.

It is also saved in `.audit\public-url.txt` if you lose it.

## 5. Leave the black window open

While that window is open, the website works for everyone you gave the link to.
If you close the window (or turn off the laptop), the website stops.

**To stop the website on purpose:** click the black window, then press
**Ctrl + C**.

---

## Things people get wrong

- **Opening an old link.** Every time you start, the link changes. If someone
  opens yesterday's link they get **Error 1033**. Send them the new LIVE link.
- **Closing the black window.** That is the website. Minimise it, don't close it.
- **Turning off the laptop.** The website goes down with it. Nothing is lost —
  double-click the file again tomorrow and it all comes back.

## If the window closes immediately or shows an error

1. Double-click the file again — the first try sometimes catches Windows still
   loading.
2. If it says `could not start` MySQL: open **XAMPP Control Panel** → **Start**
   MySQL, then double-click the file again.
3. If it says `Could not find the virtual environment`, the project was copied
   without its `venv` folder. In the project folder run:

   ```
   python -m venv venv
   venv\Scripts\pip install -r requirements.txt
   ```

## Want it on your laptop only, no public link?

Double-click `start-bhims.bat` instead, then open <http://127.0.0.1:8017/>.
Only this laptop can see it.

## Want a link that never changes?

That needs the site on a real host instead of this laptop. The free plan and the
ready-made deploy script are in `docs/DEPLOY-FREE.md`.
