import { Component, OnInit, ChangeDetectorRef, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Chart, registerables } from 'chart.js';

import { FraudeService } from '../../services/fraude.service';

// utils
import { formatarStatus, formatarPais, formatarData } from '../../utils/formatters';
import { Fraude } from '../../models/fraude.model';

Chart.register(...registerables);

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {

  @ViewChild('graficoCanvas') graficoCanvas!: ElementRef<HTMLCanvasElement>;

  fraudes: Fraude[] = [];
  totalValor: number = 0;
  chart: any;

  paginaAtual: number = 1;
  itensPorPagina: number = 10;

  constructor(
    private fraudeService: FraudeService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    this.carregarDados();
  }

  get totalPaginas(): number {
    return Math.ceil(this.fraudes.length / this.itensPorPagina);
  }

  get dadosPaginados(): any[] {
    const inicio = (this.paginaAtual - 1) * this.itensPorPagina;
    const fim = inicio + this.itensPorPagina;
    return this.fraudes.slice(inicio, fim);
  }

  mudarPagina(proxima: boolean) {
    if (proxima && this.paginaAtual < this.totalPaginas) {
      this.paginaAtual++;
    } else if (!proxima && this.paginaAtual > 1) {
      this.paginaAtual--;
    }
  }

  carregarDados() {
    this.fraudeService.getTopFraudes().subscribe({
      next: (data: any[]) => {
        this.fraudes = data.map(item => ({
          ...item,
          statusFormatado: formatarStatus(item.status),
          paisFormatado: formatarPais(item.pais),
          dataFormatada: formatarData(item.data_hora)
        }));

        this.totalValor = this.fraudes.reduce((acc, curr) => acc + (curr.valor || 0), 0);

        this.cdr.detectChanges();

        setTimeout(() => this.createChart(), 150);
      },
      error: (err) => {
        console.error('Erro ao carregar dados:', err);
      }
    });
  }

  createChart() {
    if (!this.graficoCanvas) return;

    const context = this.graficoCanvas.nativeElement.getContext('2d');
    if (!context) return;

    if (this.chart) this.chart.destroy();

    this.chart = new Chart(context, {
      type: 'bar',
      data: {
        labels: this.fraudes.slice(0, 10).map(i => "ID " + (i.id_transacao)),
        datasets: [{
          label: 'Valor da Fraude (R$)',
          data: this.fraudes.slice(0, 10).map(i => i.valor),
          backgroundColor: '#e74c3c',
          borderColor: '#c0392b',
          borderWidth: 1,
          borderRadius: 5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top'
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              callback: (value) => 'R$ ' + value
            }
          }
        }
      }
    });
  }
}