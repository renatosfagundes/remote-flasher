"""Generate the PDF manual for Remote Firmware Flasher (pt-BR) with proper accents."""
from fpdf import FPDF

FONT_DIR = r"C:\Windows\Fonts"


class Manual(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("Segoe", "", f"{FONT_DIR}\\segoeui.ttf")
        self.add_font("Segoe", "B", f"{FONT_DIR}\\segoeuib.ttf")
        self.add_font("Segoe", "I", f"{FONT_DIR}\\segoeuii.ttf")
        self.add_font("Segoe", "BI", f"{FONT_DIR}\\segoeuiz.ttf")

    def header(self):
        if self.page_no() == 1:
            return  # no header on cover
        self.set_font("Segoe", "B", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Remote Firmware Flasher \u2014 Manual do Usu\u00e1rio", align="R")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Segoe", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"P\u00e1gina {self.page_no()}/{{nb}}", align="C")

    def chapter_title(self, title):
        self.ln(4)
        self.set_font("Segoe", "B", 15)
        self.set_text_color(15, 52, 120)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(15, 52, 120)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def section_title(self, title):
        self.ln(2)
        self.set_font("Segoe", "B", 12)
        self.set_text_color(40, 80, 160)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self.set_font("Segoe", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet(self, text):
        self.set_font("Segoe", "", 10)
        self.set_text_color(30, 30, 30)
        self.cell(6, 5.5, "\u2022")
        self.multi_cell(0, 5.5, text)
        self.ln(0.5)

    def code_block(self, text):
        self.set_font("Courier", "", 9)
        self.set_fill_color(240, 240, 240)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5, text, fill=True)
        self.ln(2)

    def note_box(self, text):
        self.set_fill_color(255, 248, 220)
        self.set_draw_color(200, 180, 50)
        self.set_font("Segoe", "B", 9)
        self.set_text_color(120, 100, 0)
        self.cell(0, 6, "  Nota:", new_x="LMARGIN", new_y="NEXT", fill=True)
        self.set_font("Segoe", "", 9)
        self.multi_cell(0, 5, "  " + text, fill=True)
        self.ln(3)


def build():
    pdf = Manual()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # --- Capa ---
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Segoe", "B", 28)
    pdf.set_text_color(15, 52, 120)
    pdf.cell(0, 15, "Remote Firmware Flasher", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Segoe", "", 16)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, "Manual do Usu\u00e1rio", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Segoe", "", 12)
    pdf.cell(0, 7, "Resid\u00eancia Tecnol\u00f3gica \u2014 UFPE/CIn", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, "Sistemas Operacionais de Tempo Real", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_font("Segoe", "I", 10)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 7, "Vers\u00e3o 1.0 \u2014 Mar\u00e7o 2026", align="C", new_x="LMARGIN", new_y="NEXT")

    # --- 1. Introdu\u00e7\u00e3o ---
    pdf.add_page()
    pdf.chapter_title("1. Introdu\u00e7\u00e3o")
    pdf.body_text(
        "O Remote Firmware Flasher \u00e9 uma aplica\u00e7\u00e3o desktop que permite programar "
        "placas Arduino remotamente, atrav\u00e9s de conex\u00e3o VPN e SSH. Foi desenvolvido "
        "para a Resid\u00eancia Tecnol\u00f3gica do CIn/UFPE, permitindo que alunos gravem "
        "firmware nas placas do laborat\u00f3rio sem precisar estar fisicamente presente."
    )

    pdf.section_title("1.1 Funcionalidades")
    pdf.bullet("Conex\u00e3o VPN (SSTP) diretamente pela aplica\u00e7\u00e3o")
    pdf.bullet("Upload e grava\u00e7\u00e3o de firmware (.hex) via SCP + avrdude")
    pdf.bullet("Reset das placas via scripts PowerShell remotos")
    pdf.bullet("Terminal serial para monitorar sa\u00edda das placas em tempo real")
    pdf.bullet("Terminal SSH para executar comandos no PC remoto")
    pdf.bullet("C\u00e2mera ao vivo para visualizar as placas reagindo aos comandos")
    pdf.bullet("Suporte a m\u00faltiplos PCs e placas do laborat\u00f3rio")
    pdf.bullet("Configura\u00e7\u00e3o inicial autom\u00e1tica (primeira execu\u00e7\u00e3o)")
    pdf.bullet("Cria\u00e7\u00e3o autom\u00e1tica da pasta remota do usu\u00e1rio")

    # --- 2. Instala\u00e7\u00e3o ---
    pdf.chapter_title("2. Instala\u00e7\u00e3o")

    pdf.section_title("2.1 Execut\u00e1vel (recomendado)")
    pdf.body_text(
        "Basta baixar o arquivo RemoteFlasher.exe e executar. "
        "N\u00e3o \u00e9 necess\u00e1rio instalar Python ou qualquer depend\u00eancia."
    )

    pdf.section_title("2.2 C\u00f3digo-fonte")
    pdf.body_text("Para executar a partir do c\u00f3digo-fonte:")
    pdf.code_block(
        "git clone https://github.com/renatosfagundes/remote-flasher.git\n"
        "cd remote-flasher\n"
        "pip install -r requirements.txt\n"
        "python main.py"
    )
    pdf.body_text("Depend\u00eancias: Python 3.9+, PySide6, paramiko, requests")

    # --- 3. Primeira Execu\u00e7\u00e3o ---
    pdf.chapter_title("3. Primeira Execu\u00e7\u00e3o")
    pdf.body_text(
        "Na primeira vez que voc\u00ea abrir o aplicativo, uma janela de configura\u00e7\u00e3o "
        "ser\u00e1 exibida solicitando:"
    )
    pdf.bullet("Seu nome \u2014 usado para criar sua pasta no PC remoto")
    pdf.bullet(
        "Pasta remota \u2014 preenchida automaticamente como c:\\2026\\<seu_nome>. "
        "Essa \u00e9 a pasta no PC do laborat\u00f3rio onde seus arquivos .hex ser\u00e3o enviados."
    )
    pdf.body_text(
        "Essas configura\u00e7\u00f5es s\u00e3o salvas em %APPDATA%\\RemoteFlasher\\settings.json "
        "e persistem entre sess\u00f5es. Voc\u00ea pode limpar todas as configura\u00e7\u00f5es a "
        "qualquer momento pelo link \u2018Clear All Settings\u2019 no rodap\u00e9 da aba VPN."
    )
    pdf.body_text(
        "A pasta remota \u00e9 criada automaticamente no PC do laborat\u00f3rio na "
        "primeira opera\u00e7\u00e3o que a utilize (flash, serial, reset, etc.)."
    )

    # --- 4. Conectando \u00e0 VPN ---
    pdf.chapter_title("4. Conectando \u00e0 VPN")
    pdf.body_text("A aba VPN permite conectar-se \u00e0 rede do laborat\u00f3rio:")
    pdf.bullet("Nome da conex\u00e3o: VPN_CIN (j\u00e1 configurado)")
    pdf.bullet("Endere\u00e7o: vpn.cin.ufpe.br")
    pdf.bullet("Protocolo: SSTP")
    pdf.bullet("Usu\u00e1rio e senha: suas credenciais do CIn")
    pdf.ln(1)
    pdf.body_text(
        "Passos:\n"
        "1. Insira seu usu\u00e1rio e senha na aba VPN\n"
        "2. (Opcional) Marque \u2018Remember me\u2019 para salvar as credenciais localmente\n"
        "3. Clique em \u2018Connect VPN\u2019\n"
        "4. Aguarde a conex\u00e3o ser estabelecida (indicador verde)"
    )
    pdf.note_box(
        "Se a VPN ainda n\u00e3o estiver configurada no Windows, clique em "
        "\u2018Setup VPN\u2019 para criar a conex\u00e3o automaticamente."
    )

    pdf.section_title("4.1 Limpar Configura\u00e7\u00f5es")
    pdf.body_text(
        "O link \u2018Clear All Settings\u2019 no rodap\u00e9 da aba VPN remove todas as "
        "configura\u00e7\u00f5es salvas (credenciais VPN, pasta remota) e fecha o aplicativo. "
        "Na pr\u00f3xima execu\u00e7\u00e3o, o di\u00e1logo de primeira configura\u00e7\u00e3o "
        "ser\u00e1 exibido novamente."
    )

    # --- 5. Gravando Firmware ---
    pdf.chapter_title("5. Gravando Firmware (Flash)")
    pdf.body_text("A aba Flash permite enviar e gravar firmware nas placas:")
    pdf.body_text(
        "Passos:\n"
        "1. Selecione o PC de destino (ex: PC 217)\n"
        "2. Selecione a placa (ex: Placa 01)\n"
        "3. Selecione a porta ECU (porta COM do Arduino no PC remoto)\n"
        "4. Clique em \u2018Browse\u2019 e selecione seu arquivo .hex\n"
        "5. Clique em \u2018Flash\u2019"
    )
    pdf.body_text(
        "O aplicativo ir\u00e1 automaticamente:\n"
        "  a) Criar sua pasta remota (se n\u00e3o existir)\n"
        "  b) Enviar o arquivo .hex via SCP\n"
        "  c) Resetar a placa (se configurado)\n"
        "  d) Gravar o firmware usando avrdude\n"
        "  e) Reportar sucesso ou falha no log"
    )
    pdf.note_box(
        "Os arquivos .hex s\u00e3o gerados pelo Trampoline RTOS ap\u00f3s a compila\u00e7\u00e3o. "
        "Exemplo: lab02a_fw.hex"
    )

    # --- 6. Terminal Serial ---
    pdf.chapter_title("6. Terminal Serial")
    pdf.body_text(
        "A aba Serial permite monitorar a sa\u00edda serial das placas em tempo real "
        "atrav\u00e9s de SSH. O aplicativo executa o script serialterm.py no PC remoto "
        "e exibe a sa\u00edda no terminal."
    )
    pdf.body_text(
        "Passos:\n"
        "1. Selecione o PC e a porta COM\n"
        "2. Configure o baudrate (padr\u00e3o: 115200)\n"
        "3. Clique em \u2018Connect\u2019\n"
        "4. A sa\u00edda serial ser\u00e1 exibida em tempo real\n"
        "5. Clique em \u2018Disconnect\u2019 para encerrar"
    )

    # --- 7. Terminal SSH ---
    pdf.chapter_title("7. Terminal SSH")
    pdf.body_text(
        "A aba SSH Terminal permite executar comandos arbitr\u00e1rios no PC remoto "
        "para depura\u00e7\u00e3o ou gerenciamento de arquivos."
    )
    pdf.body_text(
        "Passos:\n"
        "1. Selecione o PC de destino\n"
        "2. Opcionalmente, defina o diret\u00f3rio de trabalho remoto\n"
        "3. Digite o comando e pressione Enter ou clique em \u2018Run\u2019\n"
        "4. A sa\u00edda ser\u00e1 exibida no terminal"
    )
    pdf.note_box(
        "O PC remoto usa Windows, ent\u00e3o use comandos Windows (dir, cd, copy, etc.) "
        "e n\u00e3o comandos Linux (ls, pwd, cp, etc.)."
    )

    # --- 8. Reset de Placas ---
    pdf.chapter_title("8. Reset de Placas")
    pdf.body_text(
        "A aba Reset permite enviar um sinal de reset para uma placa espec\u00edfica. "
        "O reset \u00e9 feito executando scripts PowerShell (ex: reset_placa_01.ps1) "
        "no PC remoto."
    )
    pdf.body_text(
        "Passos:\n"
        "1. Selecione o PC e a placa\n"
        "2. Clique em \u2018Reset\u2019\n"
        "3. Aguarde a confirma\u00e7\u00e3o no log"
    )

    # --- 9. C\u00e2mera ---
    pdf.chapter_title("9. C\u00e2mera ao Vivo")
    pdf.body_text(
        "Um painel de c\u00e2mera pode ser exibido ao lado direito da aplica\u00e7\u00e3o, "
        "mostrando o feed de v\u00eddeo do laborat\u00f3rio em tempo real. Isso permite "
        "visualizar os LEDs das placas e confirmar visualmente que o firmware "
        "est\u00e1 funcionando."
    )
    pdf.bullet("O painel aparece automaticamente nas abas Flash, Serial, SSH e Reset")
    pdf.bullet("Na aba VPN, o painel de c\u00e2mera fica oculto")
    pdf.bullet("Voc\u00ea pode mostrar/ocultar o painel clicando no bot\u00e3o da c\u00e2mera")

    # --- 10. Configura\u00e7\u00e3o dos PCs ---
    pdf.chapter_title("10. Configura\u00e7\u00e3o dos PCs")
    pdf.body_text(
        "O arquivo lab_config.py cont\u00e9m a configura\u00e7\u00e3o de todos os PCs e placas "
        "do laborat\u00f3rio. Os PCs dispon\u00edveis s\u00e3o:"
    )
    pdf.ln(1)
    pdf.set_font("Segoe", "", 9)
    pdf.set_fill_color(240, 240, 240)
    data = [
        ["PC", "IP", "M\u00e9todo Flash", "Placas"],
        ["PC 217", "172.20.36.217", "avrdude", "4 (com reset)"],
        ["PC 218", "172.20.36.218", "avrdude", "4 (sem reset)"],
        ["PC 220", "172.20.36.220", "flash.py", "4 (com reset)"],
        ["PC 221", "172.20.36.221", "avrdude", "4 (sem reset)"],
    ]
    col_widths = [25, 40, 35, 45]
    for i, row in enumerate(data):
        fill = i == 0
        if i == 0:
            pdf.set_font("Segoe", "B", 9)
        else:
            pdf.set_font("Segoe", "", 9)
        for j, cell in enumerate(row):
            pdf.cell(col_widths[j], 6, cell, border=1, fill=fill, align="C")
        pdf.ln()
    pdf.ln(3)

    pdf.body_text(
        "Cada placa possui 4 portas ECU (Arduino), uma porta de reset e um "
        "script de reset associado. As portas COM espec\u00edficas est\u00e3o documentadas "
        "em lab_config.py."
    )

    # --- 11. Solu\u00e7\u00e3o de Problemas ---
    pdf.chapter_title("11. Solu\u00e7\u00e3o de Problemas")

    pdf.section_title("VPN n\u00e3o conecta")
    pdf.bullet("Verifique se suas credenciais est\u00e3o corretas")
    pdf.bullet("Tente o bot\u00e3o \u2018Setup VPN\u2019 para recriar a conex\u00e3o")
    pdf.bullet("Verifique se outra VPN n\u00e3o est\u00e1 ativa")

    pdf.section_title("Erro ao gravar firmware")
    pdf.bullet("Verifique se a porta COM est\u00e1 correta para a placa selecionada")
    pdf.bullet("Tente resetar a placa antes de gravar novamente")
    pdf.bullet("Verifique se o arquivo .hex \u00e9 v\u00e1lido e n\u00e3o est\u00e1 corrompido")
    pdf.bullet("Verifique se o baudrate do avrdude est\u00e1 correto (padr\u00e3o: 57600)")

    pdf.section_title("Terminal serial mostra caracteres estranhos")
    pdf.bullet("Verifique se o baudrate est\u00e1 correto (deve ser 115200 para Trampoline)")
    pdf.bullet("Tente desconectar e reconectar")

    pdf.section_title("C\u00e2mera n\u00e3o carrega")
    pdf.bullet("Verifique se o PC remoto tem o servidor de c\u00e2mera ativo na porta 8080")
    pdf.bullet("Tente acessar a URL da c\u00e2mera diretamente no navegador")

    pdf.section_title("Aplicativo fecha ao clicar em bot\u00f5es")
    pdf.bullet("Isso pode indicar um erro de configura\u00e7\u00e3o")
    pdf.bullet("Tente executar a partir do c\u00f3digo-fonte (python main.py) para ver mensagens de erro no terminal")

    # --- Save ---
    out = r"c:\Users\rfagu\Codigos\Pos\RTOS\remote_flasher\Manual_RemoteFlasher.pdf"
    pdf.output(out)
    print(f"PDF created: {out} ({pdf.page_no()} pages)")


if __name__ == "__main__":
    build()
