from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from collections import defaultdict

def obter_resultados():
    print("Iniciando coleta de dados...")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    url = "https://www.flashscore.com/football/brazil/serie-a-betano/results/"
    
    try:
        print("Acessando o site...")
        driver.get(url)
        time.sleep(5)
        
        print("Carregando todos os jogos...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        matches = soup.find_all('div', class_='event__match')
        print(f"{len(matches)} jogos encontrados.")
        
        data = []
        for match in matches:
            date = match.find('div', class_='event__time').get_text(strip=True) if match.find('div', class_='event__time') else "N/A"
            home_team = match.find('div', class_='event__homeParticipant').get_text(strip=True) if match.find('div', class_='event__homeParticipant') else "N/A"
            away_team = match.find('div', class_='event__awayParticipant').get_text(strip=True) if match.find('div', class_='event__awayParticipant') else "N/A"
            home_score = match.find('span', class_='event__score--home').get_text(strip=True) if match.find('span', class_='event__score--home') else "N/A"
            away_score = match.find('span', class_='event__score--away').get_text(strip=True) if match.find('span', class_='event__score--away') else "N/A"

            data.append({
                'Data': date,
                'Mandante': home_team,
                'Visitante': away_team,
                'Gols Mandante': home_score,
                'Gols Visitante': away_score
            })
        
        return pd.DataFrame(data)
    
    except Exception as e:
        print(f"Erro durante a coleta: {e}")
        return pd.DataFrame()
    
    finally:
        driver.quit()
        print("Coleta concluída.")

def gerar_classificacao(df_resultados):
    print("\nProcessando tabela de classificação...")
    
    if df_resultados.empty:
        print("Nenhum dado de resultado disponível.")
        return pd.DataFrame()
    
    try:
        df_resultados['Gols Mandante'] = pd.to_numeric(df_resultados['Gols Mandante'], errors='coerce').fillna(0).astype(int)
        df_resultados['Gols Visitante'] = pd.to_numeric(df_resultados['Gols Visitante'], errors='coerce').fillna(0).astype(int)
    except Exception as e:
        print(f"Erro ao converter gols: {e}")
        return pd.DataFrame()
    
    estatisticas = defaultdict(lambda: {
        'pontos': 0,
        'jogos': 0,
        'vitorias': 0,
        'empates': 0,
        'derrotas': 0,
        'gols_pro': 0,
        'gols_contra': 0,
        'saldo': 0,
        'confronto_direto': defaultdict(int)
    })

    for _, jogo in df_resultados.iterrows():
        time_casa = jogo['Mandante']
        time_fora = jogo['Visitante']
        gols_casa = jogo['Gols Mandante']
        gols_fora = jogo['Gols Visitante']

        for time, gols_feitos, gols_sofridos, resultado in [
            (time_casa, gols_casa, gols_fora, gols_casa - gols_fora),
            (time_fora, gols_fora, gols_casa, gols_fora - gols_casa)
        ]:
            estatisticas[time]['jogos'] += 1
            estatisticas[time]['gols_pro'] += gols_feitos
            estatisticas[time]['gols_contra'] += gols_sofridos
            estatisticas[time]['saldo'] += (gols_feitos - gols_sofridos)
            estatisticas[time]['confronto_direto'][time_fora if time == time_casa else time_casa] += resultado

        if gols_casa > gols_fora:
            estatisticas[time_casa]['pontos'] += 3
            estatisticas[time_casa]['vitorias'] += 1
            estatisticas[time_fora]['derrotas'] += 1
        elif gols_casa < gols_fora:
            estatisticas[time_fora]['pontos'] += 3
            estatisticas[time_fora]['vitorias'] += 1
            estatisticas[time_casa]['derrotas'] += 1
        else:
            estatisticas[time_casa]['pontos'] += 1
            estatisticas[time_fora]['pontos'] += 1
            estatisticas[time_casa]['empates'] += 1
            estatisticas[time_fora]['empates'] += 1

    def calcular_aproveit(time):
        pontos_possiveis = 3 * estatisticas[time]['jogos']
        if pontos_possiveis == 0:
            return 0.0
        porcentagem = (estatisticas[time]['pontos'] / pontos_possiveis) * 100
        return float(f"{porcentagem:.2f}")

    tabela_classificacao = []
    for time in estatisticas:
        tabela_classificacao.append({
            'Equipe': time,
            'P': estatisticas[time]['pontos'],
            'J': estatisticas[time]['jogos'],
            'V': estatisticas[time]['vitorias'],
            'E': estatisticas[time]['empates'],
            'D': estatisticas[time]['derrotas'],
            'GP': estatisticas[time]['gols_pro'],
            'GC': estatisticas[time]['gols_contra'],
            'SG': estatisticas[time]['saldo'],
            '%': calcular_aproveit(time)
        })

    tabela_ordenada = sorted(tabela_classificacao, 
                           key=lambda x: (-x['P'], -x['V'], -x['SG'], -x['GP']))

    df_classificacao = pd.DataFrame(tabela_ordenada)
    df_classificacao.insert(0, 'Pos', range(1, len(df_classificacao) + 1))

    colunas = ['Pos', 'Equipe', 'P', 'J', 'V', 'E', 'D', 'GP', 'GC', 'SG', '%']
    
    return df_classificacao[colunas]

if __name__ == "__main__":
    df_resultados = obter_resultados()
    
    if not df_resultados.empty:
        df_resultados.to_csv('resultados_serie_a.csv', index=False, encoding='utf-8-sig')
        print("\nTabela de Resultados:")
        print(df_resultados.head())
        
        df_classificacao = gerar_classificacao(df_resultados)
        
        if not df_classificacao.empty:
            df_classificacao.to_csv('classificacao_serie_a.csv', index=False, encoding='utf-8-sig')
            print("\nTabela de Classificação:")
            print(df_classificacao.head())
        else:
            print("Não foi possível gerar a tabela de classificação.")
    else:
        print("Não foi possível obter os resultados dos jogos.")
        

# [As funções obter_resultados() e gerar_classificacao() permanecem EXATAMENTE iguais ao código anterior]

def gerar_html(df_resultados, df_classificacao):
    html = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Campeonato Brasileiro Série A 2025</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                color: #333;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
            }}
            h1, h2 {{
                color: #0066cc;
                text-align: center;
            }}
            h1 {{
                margin-bottom: 5px;
            }}
            h2 {{
                margin-top: 0;
                margin-bottom: 20px;
                font-size: 1.2em;
                color: #666;
            }}
            .tabela-container {{
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                padding: 20px;
                margin-bottom: 30px;
                overflow-x: auto;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }}
            th {{
                background-color: #0066cc;
                color: white;
                padding: 12px 8px;
                text-align: center;
                position: sticky;
                top: 0;
            }}
            td {{
                padding: 10px 8px;
                border-bottom: 1px solid #ddd;
                text-align: center;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            tr:hover {{
                background-color: #f1f1f1;
            }}
            .posicao-top {{
                font-weight: bold;
                color: #0066cc;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                color: #666;
                font-size: 0.9em;
            }}
            @media (max-width: 768px) {{
                .tabela-container {{
                    padding: 10px;
                }}
                th, td {{
                    padding: 8px 5px;
                    font-size: 0.9em;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Campeonato Brasileiro Série A 2025</h1>
            <h2>Estatísticas atualizadas em {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}</h2>
            
            <div class="tabela-container">
                <h2>Tabela de Classificação</h2>
                {df_classificacao.to_html(index=False, classes='tabela-classificacao', escape=False)}
            </div>
            
            <div class="tabela-container">
                <h2>Últimos Resultados</h2>
                {df_resultados.to_html(index=False, classes='tabela-resultados')}
            </div>
            
            <div class="footer">
                Dados coletados do Flashscore | Atualizado automaticamente
            </div>
        </div>
    </body>
    </html>
    """
    
    # Adiciona classes para as primeiras posições
    html = html.replace('<td>1</td>', '<td class="posicao-top">1</td>')
    html = html.replace('<td>2</td>', '<td class="posicao-top">2</td>')
    html = html.replace('<td>3</td>', '<td class="posicao-top">3</td>')
    html = html.replace('<td>4</td>', '<td class="posicao-top">4</td>')

    os.makedirs('docs', exist_ok=True)

    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Arquivo HTML gerado com sucesso: campeonato_brasileiro.html")

if __name__ == "__main__":
    df_resultados = obter_resultados()
    
    if not df_resultados.empty:
        df_classificacao = gerar_classificacao(df_resultados)
        
        if not df_classificacao.empty:
            # Formata as colunas numéricas para terem alinhamento à direita
            df_classificacao.style.set_properties(**{'text-align': 'center'})
            df_resultados.style.set_properties(**{'text-align': 'center'})
            
            gerar_html(df_resultados, df_classificacao)
            
            print("\nTabela de Resultados:")
            print(df_resultados.head())
            print("\nTabela de Classificação:")
            print(df_classificacao.head())
        else:
            print("Não foi possível gerar a tabela de classificação.")
    else:
        print("Não foi possível obter os resultados dos jogos.")


# In[ ]:




