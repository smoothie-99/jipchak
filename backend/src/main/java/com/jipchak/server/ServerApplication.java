package com.jipchak.server;

import io.github.cdimascio.dotenv.Dotenv;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class ServerApplication {

	public static void main(String[] args) {
		// .env 파일 로드
		Dotenv dotenv = Dotenv.configure()
				.directory(".") // 현재 작업 디렉토리에서 .env 찾기
				.ignoreIfMissing()
				.load();

		// 로드된 변수들을 System Property로 등록하여 Spring이 `${...}`로 참조할 수 있게 함
		dotenv.entries().forEach(entry -> {
			System.setProperty(entry.getKey(), entry.getValue());
		});

		SpringApplication.run(ServerApplication.class, args);
	}

}
