using System;
using System.Drawing;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using System.Windows.Forms;
using FFmpeg.AutoGen; // H.264 디코딩용 (남겨둠)

namespace PiCarXHost
{
    public class Form1 : Form
    {
        private string CAR_IP;
        private const int CONTROL_PORT = 9000;

        private TcpClient controlClient;
        private NetworkStream controlStream;

        private int frameCount = 0;
        private System.Diagnostics.Stopwatch fpsWatch = new System.Diagnostics.Stopwatch();

        private bool W_down = false, A_down = false, S_down = false, D_down = false;
        private volatile bool controlReady = false;

        // 요구: 기본값 -1
        private volatile int timerVar = -1;

        private System.Diagnostics.Stopwatch sw = new System.Diagnostics.Stopwatch();
        private System.Windows.Forms.Timer uiTimer;

        private Label centerTimerLabel;
        private Button restartButton;

        private byte[] recvBuffer = new byte[1024];

        // ========================== tread 수신 카운터 ==========================
        private int treadCount = 0;
        private const int TREAD_LIMIT = 6;

        public Form1(string ip)
        {
            CAR_IP = ip;

            // 전체화면 설정
            this.FormBorderStyle = FormBorderStyle.None;
            this.WindowState = FormWindowState.Maximized;
            this.TopMost = true;
            this.KeyPreview = true;
            this.Text = "PiCar-X Host TCP (Full Screen)";
            this.KeyDown += (s, e) => { if (e.KeyCode == Keys.Escape) this.Close(); };

            // 키 이벤트
            this.KeyDown += Form1_KeyDown;
            this.KeyUp += Form1_KeyUp;

            fpsWatch.Start();

            // 중앙 스톱워치 레이블 (초기에는 숨김)
            centerTimerLabel = new Label()
            {
                AutoSize = false,
                TextAlign = ContentAlignment.MiddleCenter,
                Width = 600,
                Height = 120,
                Font = new Font("Consolas", 48, FontStyle.Bold),
                Visible = false,
                BackColor = Color.FromArgb(180, 0, 0, 0),
                ForeColor = Color.White
            };
            this.Controls.Add(centerTimerLabel);

            // 오른쪽 하단 재시작 버튼
            restartButton = new Button()
            {
                Text = "재시작",
                Width = 120,
                Height = 40,
                Anchor = AnchorStyles.Bottom | AnchorStyles.Right
            };
            this.Controls.Add(restartButton);
            restartButton.Click += RestartButton_Click;

            // UI 타이머
            uiTimer = new System.Windows.Forms.Timer();
            uiTimer.Interval = 10; // 10ms
            uiTimer.Tick += UiTimer_Tick;

            // 제어 연결 스레드
            new Thread(ConnectToCar) { IsBackground = true }.Start();
        }

        protected override void OnShown(EventArgs e)
        {
            base.OnShown(e);
            CenterTimerLabelPosition();
            PositionRestartButton();
        }

        protected override void OnResize(EventArgs e)
        {
            base.OnResize(e);
            CenterTimerLabelPosition();
            PositionRestartButton();
        }

        private void CenterTimerLabelPosition()
        {
            centerTimerLabel.Left = (this.ClientSize.Width - centerTimerLabel.Width) / 2;
            centerTimerLabel.Top = (this.ClientSize.Height - centerTimerLabel.Height) / 2;
        }

        private void PositionRestartButton()
        {
            int margin = 20;
            restartButton.Left = this.ClientSize.Width - restartButton.Width - margin;
            restartButton.Top = this.ClientSize.Height - restartButton.Height - margin;
        }

        // ========== 키 입력 ==========
        private void Form1_KeyDown(object sender, KeyEventArgs e)
        {
            switch (e.KeyCode)
            {
                case Keys.W: if (!W_down) { SendCommand("won"); W_down = true; } break;
                case Keys.S: if (!S_down) { SendCommand("son"); S_down = true; } break;
                case Keys.A: if (!A_down) { SendCommand("aon"); A_down = true; } break;
                case Keys.D: if (!D_down) { SendCommand("don"); D_down = true; } break;
            }
        }

        private void Form1_KeyUp(object sender, KeyEventArgs e)
        {
            switch (e.KeyCode)
            {
                case Keys.W: SendCommand("woff"); W_down = false; break;
                case Keys.S: SendCommand("soff"); S_down = false; break;
                case Keys.A: SendCommand("aoff"); A_down = false; break;
                case Keys.D: SendCommand("doff"); D_down = false; break;
            }
        }

        // ========== 제어 연결 ==========
        private void ConnectToCar()
        {
            try
            {
                controlClient = new TcpClient();
                controlClient.Connect(CAR_IP, CONTROL_PORT);
                controlStream = controlClient.GetStream();
                controlReady = true;
                Console.WriteLine("[CONTROL] Connected to PiCar-X");

                new Thread(ControlReceiveLoop) { IsBackground = true }.Start();
            }
            catch (Exception ex)
            {
                Console.WriteLine("[CONTROL] Connection failed: " + ex.Message);
            }
        }

        private void ControlReceiveLoop()
        {
            try
            {
                while (controlReady && controlStream != null && controlStream.CanRead)
                {
                    int r = controlStream.Read(recvBuffer, 0, recvBuffer.Length);
                    if (r <= 0)
                    {
                        Console.WriteLine("[CONTROL] Remote closed connection");
                        controlReady = false;
                        break;
                    }

                    string msg = System.Text.Encoding.ASCII.GetString(recvBuffer, 0, r).Trim();
                    var parts = msg.Split(new char[] { '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries);
                    foreach (var p in parts)
                    {
                        ProcessIncomingCommand(p.Trim());
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("[CONTROL] ReceiveLoop error: " + ex.Message);
                controlReady = false;
            }
        }

        // ========== tread 처리 ==========
        private void ProcessIncomingCommand(string cmd)
        {
            Console.WriteLine("[CONTROL][IN] " + cmd);
            if (string.Equals(cmd, "tread", StringComparison.OrdinalIgnoreCase))
            {
                treadCount++;
                if (treadCount >= TREAD_LIMIT)
                {
                    SetTimerVar(5); // 타이머 멈춤
                    treadCount = 0;
                }
                else
                {
                    SetTimerVarAndStart(0); // tread 수신 시 시작
                }
            }
            else if (cmd.StartsWith("var:"))
            {
                var tail = cmd.Substring(4);
                if (int.TryParse(tail, out int v))
                {
                    SetTimerVar(v);
                }
            }
        }

        private void SetTimerVarAndStart(int v)
        {
            SetTimerVar(v);
            if (v == 0)
            {
                this.BeginInvoke((Action)(() =>
                {
                    centerTimerLabel.Visible = true;
                    if (!sw.IsRunning)
                        sw.Restart();
                    uiTimer.Start();
                }));
            }
            else if (v == 5)
            {
                this.BeginInvoke((Action)(() =>
                {
                    uiTimer.Stop();
                    sw.Stop();
                }));
            }
        }

        private void SetTimerVar(int v)
        {
            timerVar = v;
            Console.WriteLine($"[TIMER] timerVar set to {timerVar}");
            if (v == 0)
            {
                this.BeginInvoke((Action)(() =>
                {
                    centerTimerLabel.Visible = true;
                    if (!sw.IsRunning) sw.Restart();
                    uiTimer.Start();
                }));
            }
            else if (v == 5)
            {
                this.BeginInvoke((Action)(() =>
                {
                    uiTimer.Stop();
                    sw.Stop();
                }));
            }
            else if (v < 0)
            {
                this.BeginInvoke((Action)(() =>
                {
                    centerTimerLabel.Visible = false;
                    sw.Reset();
                    centerTimerLabel.Text = "00:00.00";
                }));
            }
        }

        private void SendCommand(string cmd)
        {
            try
            {
                if (controlReady && controlStream != null && controlStream.CanWrite)
                {
                    byte[] data = System.Text.Encoding.ASCII.GetBytes(cmd);
                    controlStream.Write(data, 0, data.Length);
                    controlStream.Flush();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("SendCommand error: " + ex.Message);
            }
        }

        // ========== UI 타이머 ==========
        private void UiTimer_Tick(object sender, EventArgs e)
        {
            if (timerVar == 5)
            {
                uiTimer.Stop();
                sw.Stop();
                return;
            }

            if (timerVar == 0)
            {
                var ms = sw.ElapsedMilliseconds;
                int minutes = (int)(ms / 60000);
                int seconds = (int)((ms % 60000) / 1000);
                int centiseconds = (int)((ms % 1000) / 10);
                string text = $"{minutes:D2}:{seconds:D2}.{centiseconds:D2}";
                centerTimerLabel.Text = text;
            }
        }

        private void RestartButton_Click(object sender, EventArgs e)
        {
            treadCount = 0;   // 카운터 초기화
            timerVar = -1;
            this.BeginInvoke((Action)(() =>
            {
                sw.Reset();
                centerTimerLabel.Text = "00:00.00";
                centerTimerLabel.Visible = false;
                uiTimer.Stop();
            }));
            Console.WriteLine("[TIMER] Restart pressed - timerVar set to -1 and stopwatch reset");
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            base.OnFormClosing(e);
            controlStream?.Close();
            controlClient?.Close();
        }

        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using (IPInputForm inputForm = new IPInputForm())
            {
                if (inputForm.ShowDialog() == DialogResult.OK)
                {
                    string ip = inputForm.EnteredIP;
                    Application.Run(new Form1(ip));
                }
                else
                {
                    MessageBox.Show("프로그램이 종료됩니다.", "종료", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
            }
        }
    }

    // ========================== IP 입력 폼 ==========================
    public class IPInputForm : Form
    {
        public string EnteredIP { get; private set; }
        private TextBox ipBox;

        public IPInputForm()
        {
            this.Text = "PiCar-X IP 입력";
            this.StartPosition = FormStartPosition.CenterScreen;
            this.Width = 300;
            this.Height = 150;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;

            Label label = new Label
            {
                Text = "PiCar-X IP 주소:",
                Dock = DockStyle.Top,
                Height = 30,
                TextAlign = ContentAlignment.MiddleCenter
            };
            this.Controls.Add(label);

            ipBox = new TextBox
            {
                Dock = DockStyle.Top,
                TextAlign = HorizontalAlignment.Center,
                Text = "192.168.0.14"
            };
            this.Controls.Add(ipBox);

            Button okButton = new Button { Text = "확인", Dock = DockStyle.Left, Width = 100 };
            okButton.Click += (s, e) =>
            {
                EnteredIP = ipBox.Text.Trim();
                if (string.IsNullOrEmpty(EnteredIP))
                {
                    MessageBox.Show("IP 주소를 입력하세요.", "오류", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    return;
                }
                this.DialogResult = DialogResult.OK;
                this.Close();
            };

            Button cancelButton = new Button { Text = "취소", Dock = DockStyle.Right, Width = 100 };
            cancelButton.Click += (s, e) => { this.DialogResult = DialogResult.Cancel; this.Close(); };

            Panel panel = new Panel { Dock = DockStyle.Bottom, Height = 40 };
            panel.Controls.Add(okButton);
            panel.Controls.Add(cancelButton);
            this.Controls.Add(panel);
        }
    }
}
